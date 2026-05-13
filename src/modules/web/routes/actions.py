from __future__ import annotations

from http import HTTPMethod, HTTPStatus
from time import time

from flask import session, redirect, render_template, request, url_for
from flask import Response as FlaskResponse
from secrets import token_urlsafe
from werkzeug import exceptions
from werkzeug.wrappers.response import Response

from ...utils import generate_csrf_tokens
from ...request_chaser import WorkRequestChaser, WorkRequestChaserException
from ..setup import ServiceContext
from ..utils import render_service_unavailable_button


# Register handlers capable of making infrastructure changes or authenticate users
def register_action_routes(app, ctx: ServiceContext) -> None:

    # Request chaser to get status updates from operations that spawn work requests.
    # Uses app-scoped signer for RequestChaser.
    @app.route('/r', methods=[HTTPMethod.GET])
    def work_poll() -> str:
        try:
            active_search, _, _, active_request_chaser = ctx.get_oci_services()
        except exceptions.ServiceUnavailable:
            app.logger.exception('/r user-scoped OCI services unavailable')
            return render_service_unavailable_button()

        work_request_id = request.args.get('id')
        action = request.args.get('action')
        identifier = request.args.get('identifier')
        region = request.args.get('region') or session.get('region', active_search.home_region)

        if not session.get('user'):
            raise exceptions.Unauthorized

        if not work_request_id or not action:
            return render_template('components/button.html',
                status=HTTPStatus.BAD_REQUEST)
        if region and region not in active_search.region_names:
            return render_template('components/button.html',
                status=HTTPStatus.BAD_REQUEST)

        try:
            status = active_request_chaser.get_work_request(work_request_id, region, action)
        except WorkRequestChaserException:
            app.logger.exception('exception occurred getting work request')
            return render_template('components/button.html',
                status=HTTPStatus.BAD_REQUEST,
                message='ERROR')

        if (status not in WorkRequestChaser.SUCCEEDED and
            status not in WorkRequestChaser.FAILED):
            return render_template(
                'components/button.html',
                work_request=work_request_id,
                action=action,
                message=status,
                identifier=identifier,
                region=region,
            )

        if status in WorkRequestChaser.FAILED:
            return render_template('components/button.html',
                action=action,
                status=HTTPStatus.CONFLICT,
                message=status)

        button_html = render_template('components/button.html', status=HTTPStatus.OK, message=status)

        if identifier:
            resource = active_search.get_resource_by_id(identifier, region=region)
            if action == WorkRequestChaser.EXTEND:
                safe_identifier = (identifier or '').replace('.', '-')
                if not resource:
                    card_fragment = render_template(
                        'components/card.html',
                        item={
                            'identifier': identifier,
                            'display_name': 'Resource missing after extend',
                            'resource_type': '',
                            'compartment_id': '',
                            'lifecycle_state': 'Resource missing after extend',
                            'time_created': '',
                            'defined_tags': {},
                        },
                        token='',
                        card_id=f"card-{safe_identifier}",
                        hx_swap_oob=True,
                        disable_extend=True,
                    )
                    return button_html + card_fragment

                tokens = generate_csrf_tokens(1)
                session.setdefault('csrf_tokens', {}).update(tokens)
                token = next(iter(tokens.keys()))
                card_id = f"card-{(resource.get('identifier') or '').replace('.', '-')}"
                card_fragment = render_template(
                    'components/card.html',
                    item=resource,
                    token=token,
                    card_id=card_id,
                    region=region,
                    hx_swap_oob=True,
                    disable_extend=True,
                )
                return button_html + card_fragment

            if action == WorkRequestChaser.DELETE:
                card_id = f"card-{(identifier or '').replace('.', '-')}"
                remove_fragment = f'<template hx-swap-oob="delete" id="{card_id}"></template>'
                return button_html + remove_fragment

        return button_html

    # User login redirect to authorization server if not logged in, else home page
    @app.route('/login', methods=[HTTPMethod.GET])
    def login() -> Response:
        if session.get('user'):
            return redirect(url_for('home'))
        uri = url_for('callback', _external=True)
        session['nonce'] = token_urlsafe()
        session['state'] = token_urlsafe()
        return redirect(ctx.oauth.login_redirect_uri(uri, session['nonce'], session['state']))

    # Callback page to set session on login
    @app.route('/callback', methods=[HTTPMethod.GET])
    def callback() -> Response:
        if request.args.get('state') != session.pop('state'):
            raise exceptions.BadRequest

        tok = ctx.oauth.retrieve_token(request.args.get('code', ''), session.pop('nonce'))
        try:
            # Get user context from ID Token
            userctx = ctx.oauth.build_user_context(tok['id_claims'])
        except exceptions.BadRequest:
            # If ID Token can't be verified, failover to introspection endpoint
            access_token = tok.get('access_token')
            if not access_token:
                raise
            introspection = ctx.oauth.introspect_token(access_token)
            userctx = ctx.oauth.build_user_context(tok['id_claims'], introspection)

        session.clear()
        session['user'] = userctx['user']
        session['userinfo'] = {
            'email': userctx.get('email'),
            'domain': userctx.get('domain'),
            'sub': userctx.get('sub'),
        }
        session['oauth_tokens'] = {
            'access_token': tok.get('access_token'),
            'refresh_token': tok.get('refresh_token'),
            'expires_in': int(tok.get('expires_in') or 0),
            'issued_at': int(time()),
        }
        return redirect(url_for('home'))

    # Logout endpoint clears the user session
    @app.route('/logout', methods=[HTTPMethod.GET])
    def logout() -> Response:
        session.clear()
        return redirect(url_for('home'))

    # Favicon
    @app.route('/favicon.ico', methods=[HTTPMethod.GET])
    def favicon() -> FlaskResponse:
        try:
            return app.send_static_file('favicon.ico')
        except exceptions.NotFound:
            return FlaskResponse(status=HTTPStatus.NO_CONTENT)

    # Delete actions can use user-scoped token signer if enabled
    @app.route('/delete', methods=[HTTPMethod.DELETE])
    def delete() -> str:
        if not session.get('user'):
            raise exceptions.Unauthorized

        try:
            active_search, active_deleter, _, _ = ctx.get_oci_services()
        except exceptions.ServiceUnavailable:
            app.logger.exception('/delete user-scoped OCI services unavailable')
            return render_service_unavailable_button()

        submitted_region = request.form.get('region')
        session_region = session.get('region', active_search.home_region)
        action_region = submitted_region or session_region
        identifier = request.form.get('identifier', '')

        if action_region not in active_search.region_names:
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        csrf_store = session.get('csrf_tokens') or {}
        if csrf_store.get(request.form.get('csrf_token'), True):
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        if not active_search.validate_resource(session['user'], identifier, region=action_region):
            return render_template('components/button.html', status=HTTPStatus.UNAUTHORIZED)

        if identifier == '':
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        resource = active_search.get_resource_by_id(identifier, region=action_region)
        if not resource:
            return render_template('components/button.html', status=HTTPStatus.NOT_FOUND)

        try:
            result = active_deleter.move([resource], region=action_region, compartment_id=resource.get('compartmentId'))
        except Exception:
            app.logger.exception('/delete deleter.move raised unhandled error')
            return render_template('components/button.html', status=HTTPStatus.INTERNAL_SERVER_ERROR)

        if result.ok:
            session.setdefault('csrf_tokens', {}).pop(request.form.get('csrf_token'), None)

        method = (result.metadata or {}).get('method')
        identifier_value = resource.get('identifier')
        region_value = action_region
        if method == 'force' and result.ok:
            card_id = f"card-{(identifier_value or '').replace('.', '-')}"
            button_html = render_template(
                'components/button.html',
                action=WorkRequestChaser.DELETE,
                status=result.status,
                message='SUCCESS',
                identifier=identifier_value,
                region=region_value,
            )
            remove_fragment = f'<template hx-swap-oob="delete" id="{card_id}"></template>'
            return button_html + remove_fragment

        return render_template(
            'components/button.html',
            action=WorkRequestChaser.DELETE,
            status=result.status,
            message='REQUESTING',
            work_request=result.work_request,
            identifier=identifier_value,
            region=region_value,
        )

    @app.route('/extend', methods=[HTTPMethod.POST])
    def extend() -> str:
        if not session.get('user'):
            raise exceptions.Unauthorized

        try:
            active_search, _, active_extender, _ = ctx.get_oci_services()
        except exceptions.ServiceUnavailable:
            app.logger.exception('/extend user-scoped OCI services unavailable')
            return render_service_unavailable_button()

        submitted_region = request.form.get('region')
        session_region = session.get('region', active_search.home_region)
        action_region = submitted_region or session_region
        identifier = request.form.get('identifier', '')

        if action_region not in active_search.region_names:
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        csrf_store = session.get('csrf_tokens') or {}
        if csrf_store.get(request.form.get('csrf_token'), True):
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        if not active_search.validate_resource(session['user'], identifier, region=action_region):
            return render_template('components/button.html', status=HTTPStatus.UNAUTHORIZED)

        if identifier == '':
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        resource = active_search.get_resource_by_id(identifier, region=action_region)
        if not resource:
            return render_template('components/button.html', status=HTTPStatus.NOT_FOUND)

        resource['region'] = action_region
        try:
            result = active_extender.extend(resource)
        except Exception:
            app.logger.exception('/extend extender.extend raised unhandled error')
            return render_template('components/button.html', status=HTTPStatus.INTERNAL_SERVER_ERROR)

        if result.ok:
            session.setdefault('csrf_tokens', {}).pop(request.form.get('csrf_token'), None)

        return render_template(
            'components/button.html',
            status=result.status,
            action=WorkRequestChaser.EXTEND,
            message='REQUESTING',
            work_request=result.work_request,
            identifier=resource.get('identifier'),
            region=action_region,
        )
