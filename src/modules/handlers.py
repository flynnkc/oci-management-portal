#!/usr/bin/python3.11

from http import HTTPStatus, HTTPMethod
from flask import Flask, session, redirect, render_template, url_for, request
from flask import Response as FlaskResponse
from secrets import token_urlsafe
from werkzeug import exceptions
from werkzeug.wrappers.response import Response

from .utils import generate_csrf_tokens
from .config import Configuration

from modules import create_signer
from modules.authenticator import Authenticator
from modules.search import Search, SearchError, ExpiryFilter, QueryTags
from modules.delete import Deleter
from modules.delete.extend import Extender
from modules.request_chaser import WorkRequestChaser, WorkRequestChaserException


def add_handlers(app: Flask, config: Configuration, **kwargs) -> Flask:

    # =====================
    # OCI SDK Authentication
    # =====================
    cfg, signer = create_signer(
        config.get_auth_type(),
        profile=config.get_profile(),
        location=config.get_config_file()
    )
    if config.get_log_level() == 'DEBUG':
        cfg['log_requests'] = True

    # =====================
    # Search
    # =====================
    query = QueryTags(
        config.get_mgmt_tag().namespace,
        config.get_mgmt_tag().key,
        config.get_cleanup_compartment(),
        log_level=config.get_log_level())
    
    search = Search(
        config.get_mgmt_tag().namespace,
        config.get_mgmt_tag().key,
        cfg,
        signer,
        query,
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
        signer,
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
        tag_key=config.get_filter().key or "Expires",
        handler=config.get_log_handler(),
        log_level=config.get_log_level()
    )

    # =====================
    # WorkRequestChaser
    # =====================
    request_chaser = WorkRequestChaser(
        cfg,
        signer,
        regions = search.region_names,
        log_level=config.get_log_level(),
        handler=config.get_log_handler()
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
            app.logger.exception('/ Initial search failed')
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
            days=extender.extend_period.days,
            force_delete_types=getattr(deleter, 'force_delete_types', [])
        )

    # =====================
    # Supported Resources
    # =====================
    @app.route('/resources', methods=[HTTPMethod.GET])
    def about() -> str:
        if not session.get('user'):
            app.logger.debug('/resources no user session - presenting page')
            return render_template('resources.html')

    # Deleter provides canonical display names (CamelCase)
        delete_display = Deleter.supported_delete_display_map()   # {norm: Display}
        force_display = Deleter.supported_force_display_map()     # {norm: Display}

    # Extend: extender-supported + (your rule) force-delete types also support Extend
        extend_norm = Extender.supported_extend_norm_keys() | set(force_display.keys())

        support: dict[str, list[str]] = {}

    # Add Delete actions
        for norm_key, display in delete_display.items():
            support.setdefault(display, []).append("Delete")

    # Add Extend actions, using Deleter display name when possible
        for norm_key in extend_norm:
            display = delete_display.get(norm_key) or force_display.get(norm_key) or norm_key
            support.setdefault(display, []).append("Extend")

        app.logger.debug(f'/resources rendering page for {session["user"]}')
        return render_template(
            'resources.html',
            user=session['user'],
            supported_types=dict(sorted(support.items(), key=lambda x: x[0].lower())),
            force_delete_types=sorted(force_display.values(), key=str.lower),
        )

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
    # Health Check
    # =====================
    @app.route('/health', methods=[HTTPMethod.GET])
    def health() -> Response:
        return Response(response='healthy', status=HTTPStatus.OK)

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
            if region not in search.region_names:
                app.logger.warning(f'/p invalid region requested: {region}')
                raise exceptions.BadRequest
            app.logger.debug(f'/p region: {region}')
            session['region'] = region

        try:
            app.logger.debug(f'/p getting resources for {session["user"]}')
            results = search.get_user_resources(
                session['user'],
                page=request.args.get('next_page'),
                resource=session['resource_type'],
                region=session['region'],
                # limit can be increased to reduce empty-page probability
                # limit=1000,
            )
        except SearchError:
            app.logger.exception('/p search exception occurred in pagination - returning 500')
            raise exceptions.InternalServerError

        # Server-side prefetch: skip empty pages that were fully filtered out
        items = results.data.items
        next_page = results.next_page

        max_prefetch = 2  # small cap to avoid excessive API calls
        prefetch = 0
        while (not items) and next_page and (prefetch < max_prefetch):
            app.logger.info(
                f"/p prefetching next page due to empty filtered results (attempt {prefetch + 1})"
            )
            try:
                results = search.get_user_resources(
                    session['user'],
                    page=next_page,
                    resource=session['resource_type'],
                    region=session['region'],
                )
            except SearchError:
                app.logger.exception('/p search exception occurred during prefetch - returning 500')
                raise exceptions.InternalServerError

            items = results.data.items
            next_page = results.next_page
            prefetch += 1

        tokens = generate_csrf_tokens(len(items))
        session['csrf_tokens'].update(tokens)

        app.logger.debug(f'/p returning items count: {len(items)} next_page: {next_page}')
        return render_template(
            'cards.html',
            items=items,
            next_page=next_page,
            tokens=list(tokens.keys()),
            force_delete_types=getattr(deleter, 'force_delete_types', [])
        )
    
    # =====================
    # Work Request Polling
    # =====================

    @app.route('/r', methods=[HTTPMethod.GET])
    def work_poll() -> str:
        work_request_id = request.args.get('id')
        action = request.args.get('action')
        identifier = request.args.get('identifier')
        region = request.args.get('region') or session.get('region', search.home_region)

        app.logger.debug(f'chasing work request {work_request_id}\n\taction: {action}\n\t'
                         f'identifier: {identifier}\n\tregion: {region}')

        if not session.get('user'):
            app.logger.warning('/r unauthenticated user - returning 401')
            raise exceptions.Unauthorized

        if not work_request_id or not action:
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        if region and region not in search.region_names:
            app.logger.warning(f'/r invalid region supplied: {region}')
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        try:
            status = request_chaser.get_work_request(
                work_request_id,
                region,
                action
            )
        except WorkRequestChaserException:
            app.logger.exception('exception occurred getting work request')
            return render_template('components/button.html',
                                   status=HTTPStatus.BAD_REQUEST,
                                   message='ERROR')

        app.logger.debug(f'work request status: {status}')

        if status not in WorkRequestChaser.SUCCEEDED and status not in WorkRequestChaser.FAILED:
            return render_template(
                'components/button.html',
                work_request=work_request_id,
                action=action,
                message=status,
                identifier=identifier,
                region=region,
            )

        if status in WorkRequestChaser.FAILED:
            return render_template(
                'components/button.html',
                action=action,
                status=HTTPStatus.CONFLICT,
                message=status,
            )

        def render_card_swap(resource_data: dict | None, missing_message: str, disable_extend: bool = False):
            safe_identifier = (identifier or '').replace('.', '-')
            if not resource_data:
                return render_template(
                    'components/card.html',
                    item={
                        'identifier': identifier,
                        'display_name': missing_message,
                        'resource_type': '',
                        'compartment_id': '',
                        'lifecycle_state': missing_message,
                        'time_created': '',
                        'defined_tags': {},
                    },
                    token='',
                    card_id=f"card-{safe_identifier}",
                    hx_swap_oob=True,
                    disable_extend=disable_extend,
                )

            tokens = generate_csrf_tokens(1)
            session.setdefault('csrf_tokens', {}).update(tokens)
            token = next(iter(tokens.keys()))

            card_id = f"card-{(resource_data.get('identifier') or '').replace('.', '-')}"
            return render_template(
                'components/card.html',
                item=resource_data,
                token=token,
                card_id=card_id,
                hx_swap_oob=True,
                disable_extend=disable_extend,
            )

        button_html = render_template(
            'components/button.html',
            status=HTTPStatus.OK,
            message=status,
        )
        app.logger.debug('rendered button with parameters:\n\t'
                         f'status: {HTTPStatus.OK}\n\tmessage: {status}\n\t')

        if identifier:
            resource = search.get_resource_by_id(identifier, region=region)
            if action == WorkRequestChaser.EXTEND:
                card_fragment = render_card_swap(
                    resource,
                    'Resource missing after extend',
                    disable_extend=True,
                )
                return button_html + card_fragment
            if action == WorkRequestChaser.DELETE:
                card_id = f"card-{(identifier or '').replace('.', '-')}"
                remove_fragment = f'<template hx-swap-oob="delete" id="{card_id}"></template>'
                return button_html + remove_fragment

        return button_html

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

        domain = oauth.decode_jwt(
            tok['access_token'],
            None,
            inspect=False
        )['domain']
        app.logger.debug(f'callback setting domain {domain}')

        userinfo = oauth.retrieve_userinfo(tok['access_token'])

        session.clear()
        session['user'] = f'{domain}/{userinfo["email"]}'
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
    # Favicon
    # =====================
    @app.route('/favicon.ico', methods=[HTTPMethod.GET])
    def favicon() -> FlaskResponse:
        try:
            return app.send_static_file('favicon.ico')
        except exceptions.NotFound:
            return FlaskResponse(status=HTTPStatus.NO_CONTENT)

    # =====================
    # Delete (Bulk MOVE)
    # =====================
    @app.route('/delete', methods=[HTTPMethod.DELETE])
    def delete() -> str:
        if not session.get('user'):
            app.logger.warning('/delete unauthenticated user - returning 401')
            raise exceptions.Unauthorized

        csrf_store = session.get('csrf_tokens') or {}
        if csrf_store.get(
            request.form.get('csrf_token'),
            True
        ):
            app.logger.debug(f'/delete no csrf token returning 400')
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        if not search.validate_resource(
            session['user'],
            request.form.get('identifier', ''),
            region=session['region']
        ):
            app.logger.warning(
                f'/delete Unable to validate resource {request.form.get("identifier")} '
                f'for user {session["user"]}'
            )
            return render_template('components/button.html', status=HTTPStatus.UNAUTHORIZED)

        identifier = request.form.get('identifier', '')
        app.logger.debug(
            f'/delete getting resource {identifier} in region {session["region"]}'
        )

        # Return BAD REQUEST if no identifier in form to fail early
        if identifier == '':
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        resource = search.get_resource_by_id(
            identifier,
            region=session['region']
        )

        if not resource:
            app.logger.warning(
                f'/delete no resource returned for {identifier} returning 404'
            )
            return render_template('components/button.html', status=HTTPStatus.NOT_FOUND)

        try:
            result = deleter.move(
                [resource],
                region=session['region'],
                compartment_id=resource.get('compartmentId')
            )
        except Exception as exc:
            app.logger.exception('/delete deleter.move raised unhandled error')
            return render_template(
                'components/button.html',
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        app.logger.info(
            '/delete result status=%s work_request=%s metadata=%s message=%s',
            result.status,
            result.work_request,
            result.metadata,
            result.message,
        )

        if result.ok:
            session.setdefault('csrf_tokens', {}).pop(
                request.form.get('csrf_token'),
                None
            )

        method = (result.metadata or {}).get('method')
        identifier_value = resource.get('identifier')
        region_value = session['region']

        if method == 'force' and result.ok:
            card_id = f"card-{(identifier_value or '').replace('.', '-')}"
            button_html = render_template(
                'components/button.html',
                action=WorkRequestChaser.DELETE,
                status=result.status,
                message="SUCCESS",
                identifier=identifier_value,
                region=region_value,
            )
            remove_fragment = f'<template hx-swap-oob="delete" id="{card_id}"></template>'
            return button_html + remove_fragment

        return render_template(
            'components/button.html',
            action=WorkRequestChaser.DELETE,
            status=result.status,
            message="REQUESTING",
            work_request=result.work_request,
            identifier=identifier_value,
            region=region_value,
        )

    # =====================
    # Extend Expiry
    # =====================
    @app.route('/extend', methods=[HTTPMethod.POST])
    def extend() -> str:
        if not session.get('user'):
            app.logger.warning('/extend unauthenticated user - returning 401')
            raise exceptions.Unauthorized

        csrf_store = session.get('csrf_tokens') or {}
        if csrf_store.get(
            request.form.get('csrf_token'),
            True
        ):
            app.logger.warning('/extend no csrf token returning 400')
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        if not search.validate_resource(
            session['user'],
            request.form.get('identifier', ''),
            region=session['region']
        ):
            app.logger.warning(
                f'/extend Unable to validate resource {request.form.get("identifier")} '
                f'for user {session["user"]}'
            )
            return render_template('components/button.html', status=HTTPStatus.UNAUTHORIZED)

        identifier = request.form.get('identifier', '')
        app.logger.debug(
            f'/extend getting resource {identifier or "NONE"} in region {session["region"]}'
        )

        # Return BAD REQUEST if no identifier in form to fail early
        if identifier == '':
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        # TODO Validate already makes call to get_resource_by_id: Should find way to
        # remove second call to search
        resource = search.get_resource_by_id(
            identifier,
            region=session['region']
        )

        if not resource:
            app.logger.warning(
                f'/extend No resource returned for {identifier} returning 404'
            )
            return render_template('components/button.html', status=HTTPStatus.NOT_FOUND)

        try:
            result = extender.extend(resource)
        except Exception as e:
            app.logger.exception(f'/extend extender.extend raised unhandled error {e}')
            return render_template(
                'components/button.html',
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        app.logger.info(
            (f'/extend result status={result.status} '
            f'work_request={result.work_request} metadata={result.metadata} '
            f'message={result.message}')
        )

        if result.ok:
            session.setdefault('csrf_tokens', {}).pop(
                request.form.get('csrf_token'),
                None
            )

        return render_template(
            'components/button.html',
            status=result.status,
            action=WorkRequestChaser.EXTEND,
            message="REQUESTING",
            work_request=result.work_request,
            identifier=resource.get('identifier'),
            region=session['region'],
        )
    
    @app.after_request
    def add_headers(response: FlaskResponse) -> FlaskResponse:
        #response.headers['Content-Security-Policy'] = "default-src 'self'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=()')

        # Allow upstream proxies (OCI LB, ingress) to manage HSTS/HTTPS redirects. When
        # OCI_MGMT_DASH_BEHIND_PROXY is true, ensure the proxy injects X-Forwarded-Proto
        # so Flask generates HTTPS URLs. App-level HSTS is intentionally omitted to avoid
        # conflicting with TLS termination layers.

        return response

    return app
