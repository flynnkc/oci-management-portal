#!/usr/bin/python3.11

import csv
import io
from http import HTTPStatus, HTTPMethod
from collections.abc import Mapping
from flask import Flask, session, redirect, render_template, url_for, request, jsonify
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
from modules.cost.cost_service import CostService


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

    # Keep supported types available and in memory
    delete_supported_norm = (
        set(Deleter.supported_delete_display_map().keys()) |
        set(Deleter.supported_force_display_map().keys())
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
    # Cost Service
    # =====================
    cost_service = CostService(cfg,
        signer,
        search.home_region,
        handler=config.get_log_handler(),
        log_level=config.get_log_level()
        )

    # Synchronous startup warmup: application is considered ready only after
    # initial cost cache is loaded.
    try:
        cost_service.initialize_cache(cfg["tenancy"])
    except Exception:
        app.logger.exception('Cost service startup initialization failed')
        raise

    # Keep supported types available and in memory
    extend_supported_norm = Extender.supported_extend_norm_keys()

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

    def enrich_resource_item(item) -> None:
        if isinstance(item, dict):
            rtype = item.get("resource_type", "") or item.get("resourceType", "") or ""
        else:
            rtype = getattr(item, "resource_type", "") or ""
        norm = Extender.normalize_resource_type(rtype)

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

        additional_details["supports_delete"] = norm in delete_supported_norm
        additional_details["supports_extend"] = norm in extend_supported_norm
        additional_details["owner_tag_value"] = owner_value
        additional_details["is_owner"] = is_owner
        additional_details["is_read_only"] = not is_owner

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
        session.setdefault('query_mode', 'default')
        session.setdefault(
            'initial_search_query',
            search.base_query.string('all', session['user']),
        )

        app.logger.debug('/ rendering index.html')
        return render_template(
            'index.html',
            user=session['user'],
            selections=search.resource_list,
            regions=search.region_names,
            home=search.home_region,
            current_region=session['region'],
            current_resource_type=session['resource_type'],
            days=extender.extend_period.days,
            force_delete_types=getattr(deleter, 'force_delete_types', []),
        )

    # =====================
    # Supported Resources
    # =====================

    @app.route('/resources', methods=[HTTPMethod.GET])
    def about() -> str:
        if not session.get('user'):
            app.logger.debug('/resources no user session - presenting page')
            return render_template('resources.html')

        delete_map = Deleter.supported_delete_display_map()
        extend_norm = Extender.supported_extend_norm_keys()

        resources: list[dict[str, str]] = []
        seen: set[str] = set()

        delete_count = 0
        extend_count = 0
        both_count = 0
        neither_count = 0

        for resource_type in sorted(search.resource_list, key=str.lower):
            norm = Extender.normalize_resource_type(resource_type)

            if norm in seen:
                continue
            seen.add(norm)

            is_delete = norm in delete_map
            is_extend = norm in extend_norm

            if is_delete:
                delete_count += 1
            if is_extend:
                extend_count += 1
            if is_delete and is_extend:
                both_count += 1
            if not is_delete and not is_extend:
                neither_count += 1

            if is_delete and is_extend:
                status = "both"
            elif is_delete:
                status = "delete"
            elif is_extend:
                status = "extend"
            else:
                status = "neither"

            resources.append({
                "resource_type": resource_type,
                "delete": "Delete" if is_delete else "",
                "extend": "Extend" if is_extend else "",
                "status": status,
            })

        total_count = len(resources)

        app.logger.debug(f'/resources rendering page for {session["user"]}')
        return render_template(
            'resources.html',
            user=session['user'],
            resources=resources,
            total_count=total_count,
            delete_count=delete_count,
            extend_count=extend_count,
            both_count=both_count,
            neither_count=neither_count,
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

    @app.route('/ready', methods=[HTTPMethod.GET])
    def ready() -> Response:
        if cost_service.is_cache_ready():
            return Response(response='ready', status=HTTPStatus.OK)
        return Response(response='not ready', status=HTTPStatus.SERVICE_UNAVAILABLE)

    # =====================
    # Pagination
    # =====================
    @app.route('/p', methods=[HTTPMethod.GET])
    def pagination() -> str:
        if not session.get('user'):
            app.logger.warning('/p unauthenticated user - returning 401')
            raise exceptions.Unauthorized

        is_initial_page = request.args.get('next_page') is None

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

        default_search_query = search.base_query.string(
            session.get('resource_type', 'all'),
            session['user'],
        )
        initial_search_query = session.get('initial_search_query') or search.base_query.string(
            'all',
            session['user'],
        )
        if 'initial_search_query' not in session:
            session['initial_search_query'] = initial_search_query

        reset_query = request.args.get('reset_query')
        query_mode = request.args.get('query_mode') or session.get('query_mode', 'default')
        if query_mode not in ('default', 'custom'):
            query_mode = 'default'

        if reset_query == '1':
            query_mode = 'default'
            session.pop('search_query_override', None)

        search_query_override = request.args.get('search_query')
        if query_mode == 'custom' and search_query_override is not None and reset_query != '1':
            search_query_override = search_query_override.strip()
            if search_query_override:
                session['search_query_override'] = search_query_override
            else:
                session.pop('search_query_override', None)
        elif query_mode != 'custom':
            session.pop('search_query_override', None)

        session['query_mode'] = query_mode

        delete_map = Deleter.supported_delete_display_map()
        extend_norm = Extender.supported_extend_norm_keys()
        search_query = session.get('search_query_override') if query_mode == 'custom' else None
        search_query = search_query or default_search_query

        try:
            app.logger.debug(f'/p getting resources for {session["user"]}')
            results = search.get_user_resources(
                session['user'],
                page=request.args.get('next_page'),
                resource=session['resource_type'],
                region=session['region'],
                limit=1000,
                explicit_query=search_query,
            )
        except SearchError:
            app.logger.exception('/p search exception occurred in pagination - returning 500')
            raise exceptions.InternalServerError

        items = results.data.items or []
        next_page = results.next_page
        log_unsupported_resources('pagination', items)

        max_prefetch = 2
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
                    explicit_query=search_query,
                )
            except SearchError:
                app.logger.exception('/p search exception occurred during prefetch - returning 500')
                raise exceptions.InternalServerError

            items = results.data.items or []
            next_page = results.next_page
            prefetch += 1
            log_unsupported_resources('pagination', items)

        for item in items:
            enrich_resource_item(item)

        total_count = len(items)
        tokens = generate_csrf_tokens(len(items))
        session['csrf_tokens'].update(tokens)

        app.logger.debug(f'/p returning items count: {len(items)} next_page: {next_page}')
        return render_template(
            'cards.html',
            items=items,
            next_page=next_page,
            tokens=list(tokens.keys()),
            region=session['region'],
            force_delete_types=getattr(deleter, 'force_delete_types', []),
            search_query=search_query,
            default_search_query=default_search_query,
            initial_search_query=initial_search_query,
            query_mode=query_mode,
            show_query=is_initial_page,
            total_count=total_count,
        )
    

    # =====================
    # Cost Data (async)
    # =====================

    @app.route('/costs', methods=[HTTPMethod.GET])
    def costs() -> str:
        if not session.get('user'):
            app.logger.warning('/costs unauthenticated user - returning 401')
            raise exceptions.Unauthorized

        identifiers = [i for i in request.args.getlist('identifier') if i]
        # preserve order while de-duplicating
        identifiers = list(dict.fromkeys(identifiers))

        try:
            cost_map = cost_service.get_current_costs(cfg["tenancy"])
        except Exception:
            app.logger.exception('/costs failed to load costs, falling back to zeros')
            cost_map = {}

        cost_items = [
            {
                'identifier': identifier,
                'current_cost': float(cost_map.get(identifier, 0.0) or 0.0),
            }
            for identifier in identifiers
        ]
        total_current_cost = sum(item['current_cost'] for item in cost_items)

        app.logger.debug(
            '/costs returning count=%s total_current_cost=%.2f',
            len(cost_items),
            total_current_cost,
        )

        return render_template(
            'components/cost_updates.html',
            cost_items=cost_items,
            total_current_cost=total_current_cost,
        )

    @app.route('/costs/batch', methods=[HTTPMethod.POST])
    def costs_batch() -> FlaskResponse:
        if not session.get('user'):
            app.logger.warning('/costs/batch unauthenticated user - returning 401')
            raise exceptions.Unauthorized

        payload = request.get_json(silent=True) or {}
        identifiers = payload.get('identifiers') if isinstance(payload, dict) else None
        if not isinstance(identifiers, list):
            identifiers = request.form.getlist('identifier')

        identifiers = [str(i) for i in identifiers if i]
        identifiers = list(dict.fromkeys(identifiers))[:100]

        try:
            cost_map = cost_service.get_current_costs(cfg["tenancy"])
        except Exception:
            app.logger.exception('/costs/batch failed to load costs, falling back to zeros')
            cost_map = {}

        items = [
            {
                'identifier': identifier,
                'current_cost': float(cost_map.get(identifier, 0.0) or 0.0),
            }
            for identifier in identifiers
        ]

        return jsonify({'items': items})

    @app.route('/export.csv', methods=[HTTPMethod.GET])
    def export_csv() -> FlaskResponse:
        if not session.get('user'):
            app.logger.warning('/export.csv unauthenticated user - returning 401')
            raise exceptions.Unauthorized

        resource_type = request.args.get('resource_type') or session.get('resource_type', 'all')
        region = request.args.get('region') or session.get('region', search.home_region)
        if region not in search.region_names:
            app.logger.warning(f'/export.csv invalid region requested: {region}')
            raise exceptions.BadRequest

        query_mode = request.args.get('query_mode') or session.get('query_mode', 'default')
        default_search_query = search.base_query.string(resource_type, session['user'])
        submitted_query = (request.args.get('search_query') or '').strip()
        search_query = submitted_query if query_mode == 'custom' and submitted_query else default_search_query

        all_items = []
        next_page = None

        try:
            while True:
                results = search.get_user_resources(
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
            cost_map = cost_service.get_current_costs(cfg["tenancy"])
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
            enrich_resource_item(item)
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
            error_message = request_chaser.get_work_request_error_summary(
                work_request_id,
                region,
                action,
            )
            return render_template(
                'components/button.html',
                action=action,
                status=HTTPStatus.CONFLICT,
                message=error_message or status,
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

            enrich_resource_item(resource_data)

            card_id = f"card-{(resource_data.get('identifier') or '').replace('.', '-')}"
            return render_template(
                'components/card.html',
                item=resource_data,
                token=token,
                card_id=card_id,
                region=region,
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

        # Build user context from validated ID token claims first.
        # Fall back to introspection only if required fields are missing.
        try:
            userctx = oauth.build_user_context(tok['id_claims'])
        except exceptions.BadRequest:
            access_token = tok.get('access_token')
            if not access_token:
                app.logger.warning('/callback unable to derive user from id_token and no access token available for fallback introspection')
                raise

            app.logger.info('/callback id_token claims incomplete, falling back to token introspection')
            introspection = oauth.introspect_token(access_token)
            userctx = oauth.build_user_context(tok['id_claims'], introspection)

        session.clear()
        session['user'] = userctx['user']
        session['userinfo'] = {
            'email': userctx.get('email'),
            'domain': userctx.get('domain'),
            'sub': userctx.get('sub'),
        }
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

        submitted_region = request.form.get('region')
        session_region = session.get('region', search.home_region)
        action_region = submitted_region or session_region
        identifier = request.form.get('identifier', '')

        app.logger.debug(
            '/delete request context user=%s identifier=%s submitted_region=%s session_region=%s effective_region=%s home_region=%s',
            session.get('user'),
            identifier,
            submitted_region,
            session_region,
            action_region,
            search.home_region,
        )

        if action_region not in search.region_names:
            app.logger.warning(f'/delete invalid region supplied: {action_region}')
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        csrf_store = session.get('csrf_tokens') or {}
        if csrf_store.get(
            request.form.get('csrf_token'),
            True
        ):
            app.logger.debug(f'/delete no csrf token returning 400')
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        if not search.validate_resource(
            session['user'],
            identifier,
            region=action_region
        ):
            app.logger.warning(
                '/delete ownership validation failed user=%s identifier=%s region=%s (submitted_region=%s session_region=%s)',
                session['user'],
                identifier,
                action_region,
                submitted_region,
                session_region,
            )
            return render_template('components/button.html', status=HTTPStatus.UNAUTHORIZED)

        app.logger.debug(
            '/delete ownership validated, fetching resource identifier=%s region=%s',
            identifier,
            action_region,
        )

        # Return BAD REQUEST if no identifier in form to fail early
        if identifier == '':
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        resource = search.get_resource_by_id(
            identifier,
            region=action_region
        )

        if not resource:
            app.logger.warning(
                f'/delete no resource returned for {identifier} returning 404'
            )
            return render_template('components/button.html', status=HTTPStatus.NOT_FOUND)

        try:
            result = deleter.move(
                [resource],
                region=action_region,
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
        region_value = action_region

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

        submitted_region = request.form.get('region')
        session_region = session.get('region', search.home_region)
        action_region = submitted_region or session_region
        identifier = request.form.get('identifier', '')

        app.logger.debug(
            '/extend request context user=%s identifier=%s submitted_region=%s session_region=%s effective_region=%s home_region=%s',
            session.get('user'),
            identifier,
            submitted_region,
            session_region,
            action_region,
            search.home_region,
        )

        if action_region not in search.region_names:
            app.logger.warning(f'/extend invalid region supplied: {action_region}')
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        csrf_store = session.get('csrf_tokens') or {}
        if csrf_store.get(
            request.form.get('csrf_token'),
            True
        ):
            app.logger.warning('/extend no csrf token returning 400')
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        if not search.validate_resource(
            session['user'],
            identifier,
            region=action_region
        ):
            app.logger.warning(
                '/extend ownership validation failed user=%s identifier=%s region=%s (submitted_region=%s session_region=%s)',
                session['user'],
                identifier,
                action_region,
                submitted_region,
                session_region,
            )
            return render_template('components/button.html', status=HTTPStatus.UNAUTHORIZED)

        app.logger.debug(
            '/extend ownership validated, fetching resource identifier=%s region=%s',
            identifier,
            action_region,
        )

        # Return BAD REQUEST if no identifier in form to fail early
        if identifier == '':
            return render_template('components/button.html', status=HTTPStatus.BAD_REQUEST)

        # TODO Validate already makes call to get_resource_by_id: Should find way to
        # remove second call to search
        resource = search.get_resource_by_id(
            identifier,
            region=action_region
        )

        if not resource:
            app.logger.warning(
                f'/extend No resource returned for {identifier} returning 404'
            )
            return render_template('components/button.html', status=HTTPStatus.NOT_FOUND)

        # Ensure extender has explicit region context and never relies on OCID parsing.
        resource['region'] = action_region

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
            region=action_region,
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
    
    # =================
    # Utility functions
    # =================

    def _resource_attr(resource: object, resource_dict: Mapping, *keys: str) -> str:
        for key in keys:
            value = resource_dict.get(key)
            if value:
                return value

        for key in keys:
            value = getattr(resource, key, None)
            if value:
                return value

        return ''

    def log_unsupported_resources(source: str, resources: list[dict]) -> None:
        unsupported_counts: dict[str, int] = {}
        missing_type_count = 0

        for resource in resources:
            if isinstance(resource, dict):
                resource_dict = resource
            elif hasattr(resource, 'to_dict'):
                resource_dict = resource.to_dict()
            else:
                resource_dict = vars(resource)

            resource_type = _resource_attr(
                resource,
                resource_dict,
                'resource_type',
                'resourceType',
                '_resource_type',
                'type',
            )
            if not resource_type:
                missing_type_count += 1
                continue

            norm_type = Deleter.normalize_resource_type(resource_type)
            delete_supported = norm_type in delete_supported_norm
            extend_supported = norm_type in extend_supported_norm
            if delete_supported and extend_supported:
                continue

            unsupported_counts[resource_type] = unsupported_counts.get(resource_type, 0) + 1

        if missing_type_count:
            app.logger.error(
                '[INVALID_SEARCH_RESULT] source=%s missing_resource_type count=%s',
                source,
                missing_type_count,
            )

        for resource_type, count in sorted(unsupported_counts.items()):
            app.logger.warning(
                '[UNSUPPORTED_RESOURCE] resource_type=%s count=%s',
                resource_type,
                count,
            )

    return app
