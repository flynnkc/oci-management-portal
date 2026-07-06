from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from http import HTTPMethod, HTTPStatus
from time import time

from flask import session, redirect, render_template, request, url_for
from flask import Response as FlaskResponse
from secrets import token_urlsafe
from werkzeug import exceptions
from werkzeug.wrappers.response import Response

from ...actions import Deleter, Extender
from ...request_chaser import WorkRequestChaser, WorkRequestChaserException
from ...search import Search, SearchError
from ...utils import generate_csrf_tokens
from ..setup import ServiceContext
from ..utils import render_auth_required_button, render_service_unavailable_button


# Register handlers capable of making infrastructure changes or authenticate users
def register_action_routes(app, ctx: ServiceContext) -> None:

    def _enrich_resource_item(item, deleter: Deleter, extender: Extender, search: Search) -> None:
        if isinstance(item, dict):
            rtype = item.get("resource_type", "") or item.get("resourceType", "") or ""
        else:
            rtype = getattr(item, "resource_type", "") or ""
        norm = extender.normalize_resource_type(rtype)

        if isinstance(item, dict):
            additional_details = item.get("additional_details")
            if additional_details is None:
                additional_details = {}
                item["additional_details"] = additional_details
        else:
            if not hasattr(item, "additional_details") or item.additional_details is None:
                item.additional_details = {}
            additional_details = item.additional_details

        owner_value = ''
        if isinstance(item, dict):
            defined_tags = item.get("defined_tags", {}) or item.get("definedTags", {}) or {}
        else:
            defined_tags = getattr(item, "defined_tags", None) or {}
        if isinstance(defined_tags, Mapping):
            owner_value = str(
                (
                    defined_tags.get(search.tag, {}) or {}
                ).get(search.key, '') or ''
            )

        is_owner = bool(owner_value) and owner_value.lower() == session['user'].lower()

        additional_details["supports_delete"] = norm in deleter.supported_norm_keys()
        additional_details["supports_extend"] = norm in extender.supported_norm_keys()
        additional_details["owner_tag_value"] = owner_value
        additional_details["is_owner"] = is_owner
        additional_details["is_read_only"] = not is_owner

    # Request chaser gets status updates using the app-scoped signer. Search and
    # mutating actions remain user-scoped when user-scoped OCI calls are enabled.
    @app.route('/r', methods=[HTTPMethod.GET])
    def work_poll() -> str:
        if not session.get('user'):
            raise exceptions.Unauthorized

        work_request_id = request.args.get('id')
        action = request.args.get('action')
        identifier = request.args.get('identifier')
        region = request.args.get('region') or session.get('region', ctx.search.home_region)

        if not work_request_id or not action:
            return render_template('components/button.html',
                status=HTTPStatus.BAD_REQUEST)
        if region and region not in ctx.search.region_names:
            return render_template('components/button.html',
                status=HTTPStatus.BAD_REQUEST)

        try:
            status = ctx.request_chaser.get_work_request(work_request_id, region, action)
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
            if action == WorkRequestChaser.EXTEND:
                safe_identifier = (identifier or '').replace('.', '-')
                try:
                    active_search, _, _ = ctx.get_oci_services()
                    resource = active_search.get_resource_by_id(identifier, region=region)
                except exceptions.Unauthorized:
                    app.logger.info('/r extend completed but user-scoped OCI session expired before card refresh')
                    return button_html
                except exceptions.ServiceUnavailable:
                    app.logger.exception('/r extend completed but user-scoped OCI services unavailable for card refresh')
                    return button_html

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

        # Invalidate any cache entries tied to a previous login token before replacing session.
        ctx.clear_user_token_exchange_cache()
        session.clear()
        session['user'] = userctx['user']
        session['userinfo'] = {
            'email': userctx.get('email'),
            'domain': userctx.get('domain'),
            'sub': userctx.get('sub'),
        }
        session['oauth_tokens'] = {
            'access_token': tok.get('access_token'),
            'expires_in': int(tok.get('expires_in') or 0),
            'issued_at': int(time()),
        }
        return redirect(url_for('home'))

    # Logout endpoint clears the user session
    @app.route('/logout', methods=[HTTPMethod.GET])
    def logout() -> Response:
        ctx.clear_user_token_exchange_cache()
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
            active_search, active_deleter, _ = ctx.get_oci_services()
        except exceptions.Unauthorized:
            app.logger.info('/delete user-scoped OCI session expired or invalid')
            ctx.clear_user_token_exchange_cache()
            session.clear()
            return render_auth_required_button()
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
            result = active_deleter.delete(resource, region=action_region, compartment_id=resource.get('compartmentId'))
        except Exception:
            app.logger.exception('/delete deleter.delete raised unhandled error')
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
            active_search, _, active_extender = ctx.get_oci_services()
        except exceptions.Unauthorized:
            app.logger.info('/extend user-scoped OCI session expired or invalid')
            ctx.clear_user_token_exchange_cache()
            session.clear()
            return render_auth_required_button()
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

    @app.route('/export.csv', methods=[HTTPMethod.GET])
    def export_csv() -> FlaskResponse | str:
        if not session.get('user'):
            app.logger.warning('/export.csv unauthenticated user - returning 401')
            raise exceptions.Unauthorized

        try:
            active_search, active_delete, active_extend = ctx.get_oci_services()
        except exceptions.Unauthorized:
            app.logger.info('/export.csv user-scoped OCI session expired or invalid')
            ctx.clear_user_token_exchange_cache()
            session.clear()
            raise
        except exceptions.ServiceUnavailable:
            app.logger.exception('/export.csv user-scoped OCI services unavailable')
            return render_service_unavailable_button()

        resource_type = request.args.get('resource_type') or session.get('resource_type', 'all')
        region = request.args.get('region') or session.get('region', active_search.home_region)
        if region not in active_search.region_names:
            app.logger.warning(f'/export.csv invalid region requested: {region}')
            raise exceptions.BadRequest

        query_mode = request.args.get('query_mode') or session.get('query_mode', 'default')
        default_search_query = active_search.base_query.string(resource_type, session['user'])
        submitted_query = (request.args.get('search_query') or '').strip()
        search_query = submitted_query if query_mode == 'custom' and submitted_query else default_search_query

        all_items = []
        next_page = None

        try:
            while True:
                results = active_search.get_user_resources(
                    session['user'],
                    page=next_page,
                    resource=resource_type,
                    region=region,
                    limit=1000,
                    explicit_query=search_query,
                )
                batch = results.data.items or []
                all_items.extend(batch)
                next_page = results.next_page
                if not next_page:
                    break
        except SearchError:
            app.logger.exception('/export.csv search exception occurred - returning 500')
            raise exceptions.InternalServerError

        try:
            cost_map = ctx.cost_service.get_current_costs(ctx.cfg["tenancy"])
        except Exception:
            app.logger.exception('/export.csv failed to load costs, falling back to zeros')
            cost_map = {}

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'resource_name',
            'resource_ocid',
            'resource_type',
            'region',
            'compartment_ocid',
            'compartment_path',
            'lifecycle_state',
            'created_time',
            'owner_tag_value',
            'current_monthly_cost',
            'is_owner',
            'supports_delete',
            'supports_extend',
            'search_query_used',
        ])

        for item in all_items:
            _enrich_resource_item(item, active_delete, active_extend, active_search)
            identifier = getattr(item, "identifier", "") or ""
            additional_details = getattr(item, "additional_details", None) or {}

            writer.writerow([
                getattr(item, "display_name", "") or "",
                identifier,
                getattr(item, "resource_type", "") or "",
                region,
                getattr(item, "compartment_id", "") or "",
                additional_details.get('compartmentPath', ''),
                getattr(item, "lifecycle_state", "") or "",
                getattr(item, "time_created", "") or "",
                additional_details.get('owner_tag_value', ''),
                float(cost_map.get(identifier, 0.0) or 0.0),
                str(additional_details.get('is_owner', False)).lower(),
                str(additional_details.get('supports_delete', False)).lower(),
                str(additional_details.get('supports_extend', False)).lower(),
                search_query,
            ])

        csv_body = output.getvalue()
        output.close()

        response = FlaskResponse(csv_body, mimetype='text/csv')
        response.headers['Content-Disposition'] = (
            f'attachment; filename="oci-resources-{region}-{resource_type}.csv"'
        )
        return response
