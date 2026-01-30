#!/usr/bin/python3.11

from http import HTTPStatus, HTTPMethod
from flask import Flask, session, redirect, render_template, url_for, request
from secrets import token_urlsafe
from werkzeug import exceptions
from werkzeug.wrappers.response import Response

from .utils import generate_csrf_tokens
from .config import Configuration

from modules import create_signer
from modules.authenticator import Authenticator
from modules.search import Search, SearchError, ExpiryFilter
from modules.delete import Deleter
from modules.delete.extend import Extender


def add_handlers(app: Flask, config: Configuration, **kwargs) -> Flask:

    # =====================
    # OCI SDK Authentication
    # =====================
    cfg, signer = create_signer(
        config.get_auth_type(),
        profile=config.get_profile(),
        location=config.get_config_file()
    )

    # =====================
    # Search
    # =====================
    search = Search(
        config.get_mgmt_tag().namespace,
        config.get_mgmt_tag().key,
        cfg,
        signer=signer,
        handler=config.get_log_handler(),
        log_level=config.get_log_level()
    )

    if config.get_filter().key:
        search.set_filter(
            ExpiryFilter(
                config.get_filter().namespace,
                config.get_filter().key,
                log_level=app.logger.getEffectiveLevel()
            )
        )

    # =====================
    # Deleter (Bulk Move)
    # =====================
    deleter = Deleter(
        cfg,
        config.get_cleanup_compartment(),
        signer=signer,
        regions=search.region_names,
        handler=config.get_log_handler(),
        log_level=config.get_log_level()
    )

    # =====================
    # Extender
    # =====================
    extender = Extender(
        cfg,
        signer=signer,
        tag_namespace=config.get_mgmt_tag().namespace,
        tag_key=config.get_mgmt_tag().key,
        handler=config.get_log_handler(),
        log_level=config.get_log_level()
    )

    # =====================
    # OIDC
    # =====================
    oauth = Authenticator(
        config.get_idm_endpoint(),
        config.get_idm_client_id(),
        config.get_idm_client_secret(),
        handler=config.get_log_handler(),
        log_level=config.get_log_level()
    )

    # =====================
    # Home
    # =====================
    @app.route('/', methods=[HTTPMethod.GET])
    def home() -> str:
        if not session.get('user'):
            app.logger.debug('/ no user session - presenting homepage')
            return render_template('index.html')

        session.setdefault('resource_type', 'all')
        session.setdefault('region', search.home_region)
        session.setdefault('csrf_tokens', {})

        try:
            app.logger.debug(f'/ getting resources for user {session["user"]}')
            results = search.get_user_resources(
                session['user'],
                resource=session['resource_type'],
                region=session['region']
            )
            items = results.data.items
            next_page = results.next_page
            app.logger.debug(f'/ returned {len(items)} items')
        except SearchError:
            app.logger.exception("/ Initial search failed")
            items = []
            next_page = None

        tokens = generate_csrf_tokens(len(items))
        session['csrf_tokens'].update(tokens)

        app.logger.debug('/ rendering index.html')
        return render_template(
            'index.html',
            user=session['user'],
            selections=search.resource_list,
            regions=search.region_names,
            home=search.home_region,
            items=items,
            next_page=next_page,
            tokens=list(tokens.keys()),
            days=extender.extend_period.days
        )
    
    # =====================
    # Supported Resources
    # =====================
    @app.route('/resources', methods=[HTTPMethod.GET])
    def about() -> str:
        if not session.get('user'):
            app.logger.debug('/resources no user session - presenting page')
            return render_template('resources.html')
        
        app.logger.debug(f'/resources rendering page for {session["user"]}')
        return render_template('resources.html',
            user=session['user'],
            supported_types=sorted(Deleter.BULK_SUPPORTED_TYPES.union(
                Extender.BULK_EXTEND_SUPPORTED_TYPES)))
    
    # =====================
    # Issues
    # =====================
    @app.route('/issues', methods=[HTTPMethod.GET])
    def issues() -> str:
        if not session.get('user'):
            app.logger.debug('/issues no user session - presenting page')
            return render_template('issues.html')
        
        app.logger.debug(f'/issues rendering page for {session["user"]}')
        return render_template('issues.html', user=session['user'])

    # =====================
    # Pagination
    # =====================
    @app.route('/p', methods=[HTTPMethod.GET])
    def pagination() -> str:
        if not session.get('user'):
            app.logger.warning('/p unauthenticated user - returning 401')
            raise exceptions.Unauthorized

        resource_type = request.args.get('resource_type')
        if resource_type:
            app.logger.debug(f'/p resource type: {resource_type}')
            session['resource_type'] = resource_type

        region = request.args.get('region')
        if region:
            app.logger.debug(f'/p region: {region}')
            session['region'] = region

        try:
            app.logger.debug(f'/p getting resources for {session["user"]}')
            results = search.get_user_resources(
                session['user'],
                page=request.args.get('next_page'),
                resource=session['resource_type'],
                region=session['region']
            )
        except SearchError:
            app.logger.exception('/p search exception occurred in pagination - returning 500')
            raise exceptions.InternalServerError

        items = results.data.items
        tokens = generate_csrf_tokens(len(items))
        session['csrf_tokens'].update(tokens)

        app.logger.debug(f'/p returning items count: {len(items)}')
        return render_template(
            'cards.html',
            items=items,
            next_page=results.next_page,
            tokens=list(tokens.keys())
        )

    # =====================
    # Login
    # =====================
    @app.route('/login', methods=[HTTPMethod.GET])
    def login() -> Response:
        if session.get('user'):
            app.logger.warning(f'/login user accessing page: {session.get("user")}')
            return redirect(url_for('home'))

        
        uri = url_for('callback', _external=True)
        session['nonce'] = token_urlsafe()
        session['state'] = token_urlsafe()

        app.logger.debug(f'/login redirected unauthenticated user to {uri}')
        return redirect(
            oauth.login_redirect_uri(
                uri,
                session['nonce'],
                session['state']
            )
        )

    # =====================
    # Callback
    # =====================
    @app.route('/callback', methods=[HTTPMethod.GET])
    def callback() -> Response:
        if request.args.get('state') != session.pop('state'):
            app.logger.warning('/callback reached without state - returning 400')
            raise exceptions.BadRequest

        tok = oauth.retrieve_token(
            request.args.get('code', ''),
            session.pop('nonce')
        )
        app.logger.debug(f'/callback retrieved token {tok}')

        # Getting domain info here. As I see it there are 4 options for getting the 
        # user's domain:
        # 1. Hardcode it
        # 2. Get it from configuration files (requires IAM get for domain)
        # 3. Get it via unverified token (seen here)
        # 4. Add host as secondary audience on JWT (complicates app configuration)
        domain = oauth.decode_jwt(tok['access_token'], None, inspect=False)['domain']
        app.logger.debug(f'callback setting domain {domain}')

        # Userinfo from domain userinfo endpoint to offload verification to domain
        userinfo = oauth.retrieve_userinfo(tok['access_token'])

        session.clear()
        session['user'] = f"{domain}/{userinfo['email']}"
        session['jwt'] = tok
        session['userinfo'] = userinfo
        app.logger.debug(f'/callback session set for user {session["user"]}')

        return redirect(url_for('home'))

    # =====================
    # Logout
    # =====================
    @app.route('/logout', methods=[HTTPMethod.GET])
    def logout() -> Response:
        app.logger.debug(f'logging out user {session["user"]}')
        session.clear()
        return redirect(url_for('home'))

    # =====================
    # Delete (Bulk MOVE)
    # =====================
    @app.route('/delete', methods=[HTTPMethod.DELETE])
    def delete() -> str:
        if session.get('csrf_tokens').get(
            request.form.get('csrf_token'),
            True
        ):
            app.logger.debug(f'/delete no csrf token returning 400')
            return render_template('button.html', status=HTTPStatus.BAD_REQUEST)

        if not search.validate_resource(
            session['user'],
            request.form.get('identifier', ''),
            region=session['region']
        ):
            app.logger.warning(
                f'/delete Unable to validate resource {request.form.get("identifier")}'
                f' for user {session["user"]}')
            return render_template('button.html', status=HTTPStatus.UNAUTHORIZED)

        app.logger.debug(f'/delete getting resource {request.form.get(
            "identifier")} in region {session["region"]}')
        resource = search.get_resource_by_id(
            request.form.get('identifier', ''),
            region=session['region']
        )

        if not resource:
            app.logger.warning(f'/delete no resource returned for {request.form.get(
                "identifier")} returning 404')
            return render_template(
                'button.html',
                status=HTTPStatus.NOT_FOUND
            )

        result = deleter.move(
            [resource],
            region=session['region'],
            compartment_id=resource.get("compartmentId")
        )
        app.logger.debug(f'/delete deleter move result: {result}')

        if result in (200, 202):
            session['csrf_tokens'].pop(
                request.form.get('csrf_token'),
                None
            )

        return render_template('button.html', status=result)

    # =====================
    # Extend Expiry
    # =====================
    @app.route('/extend', methods=[HTTPMethod.POST])
    def extend() -> str:
        if session.get('csrf_tokens').get(
            request.form.get('csrf_token'),
            True
        ):
            app.logger.warning('/extend no csrf token returning 400')
            return render_template('button.html', status=HTTPStatus.BAD_REQUEST)

        if not search.validate_resource(
            session['user'],
            request.form.get('identifier', ''),
            region=session['region']
        ):
            app.logger.warning(f'/extend Unable to validate resource {request.form.get("identifier")}'
            f' for user {session["user"]}')
            return render_template('button.html', status=HTTPStatus.UNAUTHORIZED)

        app.logger.debug(f'/extend getting resource {request.form.get("identifier")}'
                         f' in region {session["region"]}')
        resource = search.get_resource_by_id(
            request.form.get('identifier', ''),
            region=session['region']
        )

        if not resource:
            app.logger.warning(f'/extend No resource returned for {request.form.get(
                "identifier")} returning 404')
            return render_template(
                'button.html',
                status=HTTPStatus.NOT_FOUND
            )

        result = extender.extend(resource)
        app.logger.debug(f'/extend extender extend result: {result}')

        if result == HTTPStatus.OK:
            session['csrf_tokens'].pop(
                request.form.get('csrf_token'),
                None
            )

        return render_template('button.html', status=result)

    return app

