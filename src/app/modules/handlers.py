#!/usr/bin/python3.11

from http import HTTPStatus, HTTPMethod
from flask import Flask, session, redirect, render_template, url_for, request
from secrets import token_urlsafe
from werkzeug import exceptions

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
    def home():
        if not session.get('user'):
            return render_template('index.html')

        session.setdefault('resource_type', 'all')
        session.setdefault('region', search.home_region)
        session.setdefault('csrf_tokens', {})

        try:
            results = search.get_user_resources(
                session['user'],
                resource=session['resource_type'],
                region=session['region']
            )
            items = results.data.items
            next_page = results.next_page
        except SearchError:
            app.logger.exception("Initial search failed")
            items = []
            next_page = None

        tokens = generate_csrf_tokens(len(items))
        session['csrf_tokens'].update(tokens)

        return render_template(
            'index.html',
            user=session['user'],
            selections=search.resource_list,
            regions=search.region_names,
            home=search.home_region,
            items=items,
            next_page=next_page,
            tokens=list(tokens.keys())
        )

    # =====================
    # Pagination
    # =====================
    @app.route('/p', methods=[HTTPMethod.GET])
    def pagination():
        if not session.get('user'):
            raise exceptions.Unauthorized

        if request.args.get('resource_type'):
            session['resource_type'] = request.args.get('resource_type')

        if request.args.get('region'):
            session['region'] = request.args.get('region')

        try:
            results = search.get_user_resources(
                session['user'],
                page=request.args.get('next_page'),
                resource=session['resource_type'],
                region=session['region']
            )
        except SearchError:
            raise exceptions.InternalServerError

        items = results.data.items
        tokens = generate_csrf_tokens(len(items))
        session['csrf_tokens'].update(tokens)

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
    def login():
        if session.get('user'):
            return redirect(url_for('home'))

        uri = url_for('callback', _external=True)
        session['nonce'] = token_urlsafe()
        session['state'] = token_urlsafe()

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
    def callback():
        if request.args.get('state') != session.pop('state'):
            raise exceptions.BadRequest

        tok = oauth.retrieve_token(
            request.args.get('code'),
            session.pop('nonce')
        )

        # Getting domain info here. As I see it there are 4 options for getting the 
        # user's domain:
        # 1. Hardcode it
        # 2. Get it from configuration files (requires IAM get for domain)
        # 3. Get it via unverified token (seen here)
        # 4. Add host as secondary audience on JWT (complicates app configuration)
        domain = oauth.decode_jwt(tok['access_token'], None, inspect=False)['domain']

        # Userinfo from domain userinfo endpoint to offload verification to domain
        userinfo = oauth.retrieve_userinfo(tok['access_token'])

        session.clear()
        session['user'] = f"{domain}/{userinfo['email']}"
        session['jwt'] = tok
        session['userinfo'] = userinfo

        return redirect(url_for('home'))

    # =====================
    # Logout
    # =====================
    @app.route('/logout', methods=[HTTPMethod.GET])
    def logout():
        session.clear()
        return redirect(url_for('home'))

    # =====================
    # Delete (Bulk MOVE)
    # =====================
    @app.route('/delete', methods=[HTTPMethod.DELETE])
    def delete():
        if session.get('csrf_tokens').get(
            request.form.get('csrf_token'),
            True
        ):
            return render_template('button.html', status=HTTPStatus.BAD_REQUEST)

        if not search.validate_resource(
            session['user'],
            request.form.get('identifier'),
            region=session['region']
        ):
            return render_template('button.html', status=HTTPStatus.UNAUTHORIZED)

        resource = search.get_resource_by_id(
            request.form.get('identifier'),
            region=session['region']
        )

        if not resource:
            return render_template(
                'button.html',
                status=HTTPStatus.NOT_FOUND
            )

        result = deleter.move(
            [resource],
            region=session['region'],
            compartment_id=resource.get("compartmentId")
        )

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
    def extend():
        if session.get('csrf_tokens').get(
            request.form.get('csrf_token'),
            True
        ):
            return render_template('button.html', status=HTTPStatus.BAD_REQUEST)

        if not search.validate_resource(
            session['user'],
            request.form.get('identifier'),
            region=session['region']
        ):
            return render_template('button.html', status=HTTPStatus.UNAUTHORIZED)

        resource = search.get_resource_by_id(
            request.form.get('identifier'),
            region=session['region']
        )

        if not resource:
            return render_template(
                'button.html',
                status=HTTPStatus.NOT_FOUND
            )

        result = extender.extend(resource)

        if result == HTTPStatus.OK:
            session['csrf_tokens'].pop(
                request.form.get('csrf_token'),
                None
            )

        return render_template('button.html', status=result)

    return app

