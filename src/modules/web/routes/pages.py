from __future__ import annotations

from collections.abc import Mapping
from http import HTTPMethod, HTTPStatus

from flask import session, render_template, request, jsonify
from werkzeug import exceptions
from werkzeug.wrappers.response import Response

from ...search import SearchError
from ...utils import generate_csrf_tokens
from ..setup import ServiceContext
from ..utils import log_unsupported_resources, render_auth_required_button, render_service_unavailable_button


# Register handlers that don't modify resources in OCI
def register_page_routes(app, ctx: ServiceContext) -> None:

    # Home page
    @app.route('/', methods=[HTTPMethod.GET])
    def home() -> str:
        if not session.get('user'):
            app.logger.debug('/ no user session - presenting homepage')
            return render_template('index.html')

        session.setdefault('resource_type', 'all')
        session.setdefault('region', ctx.search.home_region)
        session.setdefault('csrf_tokens', {})
        session.setdefault('query_mode', 'default')
        session.setdefault(
            'initial_search_query',
            ctx.search.base_query.string('all', session['user']),
        )

        app.logger.debug('/ rendering index.html')
        return render_template(
            'index.html',
            user=session['user'],
            selections=ctx.search.resource_list,
            regions=ctx.search.region_names,
            home=ctx.search.home_region,
            current_region=session['region'],
            current_resource_type=session['resource_type'],
            days=ctx.extender.extend_period.days,
        )

    # Supported Resources page
    @app.route('/resources', methods=[HTTPMethod.GET])
    def about() -> str:
        if not session.get('user'):
            app.logger.debug('/resources no user session - presenting page')
            return render_template('resources.html')

        delete_norm = ctx.deleter.supported_norm_keys()
        extend_norm = ctx.extender.supported_norm_keys()

        resources: list[dict[str, str]] = []
        seen: set[str] = set()
        delete_count = extend_count = both_count = neither_count = 0

        for resource_type in sorted(ctx.search.resource_list, key=str.lower):
            norm = ctx.deleter.normalize_resource_type(resource_type)
            if norm in seen:
                continue
            seen.add(norm)

            is_delete = norm in delete_norm
            is_extend = norm in extend_norm
            delete_count += int(is_delete)
            extend_count += int(is_extend)
            both_count += int(is_delete and is_extend)
            neither_count += int((not is_delete) and (not is_extend))

            if is_delete and is_extend:
                status = 'both'
            elif is_delete:
                status = 'delete'
            elif is_extend:
                status = 'extend'
            else:
                status = 'neither'

            resources.append({
                'resource_type': resource_type,
                'delete': 'Delete' if is_delete else '',
                'extend': 'Extend' if is_extend else '',
                'status': status,
            })

        return render_template(
            'resources.html',
            user=session['user'],
            resources=resources,
            total_count=len(resources),
            delete_count=delete_count,
            extend_count=extend_count,
            both_count=both_count,
            neither_count=neither_count,
        )

    # Issues page to redirect to github issues
    @app.route('/issues', methods=[HTTPMethod.GET])
    def issues() -> str:
        if not session.get('user'):
            app.logger.debug('/issues no user session - presenting page')
            return render_template('issues.html')
        return render_template('issues.html', user=session['user'])

    # Health check
    @app.route('/health', methods=[HTTPMethod.GET])
    def health() -> Response:
        return Response(response='healthy', status=HTTPStatus.OK)

    # Readiness check waits on CostService to init cache
    @app.route('/ready', methods=[HTTPMethod.GET])
    def ready() -> Response:
        if ctx.cost_service.is_cache_ready():
            return Response(response='ready', status=HTTPStatus.OK)
        return Response(response='not ready', status=HTTPStatus.SERVICE_UNAVAILABLE)

    # Search endpoint interacts with the Search class to get all resources belonging
    # to the user. Defaults to paginating through results until done. Likely to be
    # an expensive function due to heavy network utilization. Will use user token
    # signer if available.
    @app.route('/p', methods=[HTTPMethod.GET])
    def pagination() -> str:
        if not session.get('user'):
            raise exceptions.Unauthorized

        try:
            services = ctx.get_oci_services(search=True, deleter=True, extender=True)
            active_search = services['search']
            active_deleter = services['deleter']
            active_extender = services['extender']
        except exceptions.Unauthorized:
            app.logger.info('/p user-scoped OCI session expired or invalid')
            ctx.clear_user_token_exchange_cache()
            session.clear()
            return render_auth_required_button()
        except exceptions.ServiceUnavailable:
            app.logger.exception('/p user-scoped OCI services unavailable')
            return render_service_unavailable_button()

        is_initial_page = request.args.get('next_page') is None
        resource_type = request.args.get('resource_type')
        if resource_type:
            session['resource_type'] = resource_type

        region = request.args.get('region')
        if region:
            if region not in active_search.region_names:
                raise exceptions.BadRequest
            session['region'] = region

        delete_norm = active_deleter.supported_norm_keys()
        extend_norm = active_extender.supported_norm_keys()
        force_delete_norm = active_deleter.force_delete_norm_keys()
        default_search_query = active_search.base_query.string(
            session.get('resource_type', 'all'),
            session['user'],
        )
        initial_search_query = session.get('initial_search_query') or active_search.base_query.string(
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
        search_query = session.get('search_query_override') if query_mode == 'custom' else None
        search_query = search_query or default_search_query

        # Search for all resources or return 500 if an error occurs
        try:
            results = active_search.get_user_resources(
                session['user'],
                page=request.args.get('next_page'),
                resource=session['resource_type'],
                region=session['region'],
                limit=1000,
                explicit_query=search_query,
            )
        except SearchError:
            raise exceptions.InternalServerError

        # Loop through any remaining pages
        items = []
        while True:
            page_items = results.data.items or []
            items.extend(page_items)
            log_unsupported_resources(
                app,
                'pagination',
                page_items,
                normalize_resource_type=active_deleter.normalize_resource_type,
                delete_supported_norm=ctx.delete_supported_norm,
                extend_supported_norm=ctx.extend_supported_norm,
            )

            next_page = results.next_page
            if not next_page:
                break

            try:
                results = active_search.get_user_resources(
                    session['user'],
                    page=next_page,
                    resource=session['resource_type'],
                    region=session['region'],
                    limit=1000,
                    explicit_query=search_query,
                )
            except SearchError:
                raise exceptions.InternalServerError

        # Normalize resource type and add action support identifiers
        for item in items:
            norm = active_deleter.normalize_resource_type(getattr(item, 'resource_type', '') or '')
            if not hasattr(item, 'additional_details') or item.additional_details is None:
                item.additional_details = {}
            item.additional_details['supports_delete'] = norm in delete_norm
            item.additional_details['supports_extend'] = norm in extend_norm
            item.additional_details['supports_force_delete'] = norm in force_delete_norm

            defined_tags = getattr(item, 'defined_tags', None) or {}
            owner_value = ''
            expiration_value = ''
            if isinstance(defined_tags, Mapping):
                owner_value = str(
                    (
                        defined_tags.get(active_search.tag, {}) or {}
                    ).get(active_search.key, '') or ''
                )
                filter_tag = getattr(active_search.filter, 'tag', '') or ''
                filter_key = getattr(active_search.filter, 'key', '') or ''
                if filter_tag and filter_key:
                    expiration_value = str(
                        (
                            defined_tags.get(filter_tag, {}) or {}
                        ).get(filter_key, '') or ''
                    )

            is_owner = (
                bool(owner_value)
                and owner_value.strip().lower() == session['user'].strip().lower()
            )
            item.additional_details['owner_tag_value'] = owner_value
            item.additional_details['expiration_value'] = expiration_value
            item.additional_details['is_owner'] = is_owner
            item.additional_details['is_read_only'] = not is_owner

        # Generate and assign CSRF tokens by identifier only on supported resources
        actionable_identifiers = [
            getattr(item, 'identifier', '')
            for item in items
            if (
                getattr(item, 'additional_details', {})
                and (
                    item.additional_details.get('supports_delete')
                    or item.additional_details.get('supports_extend')
                )
                and getattr(item, 'identifier', '')
            )
        ]

        generated_tokens = generate_csrf_tokens(len(actionable_identifiers))
        tokens_by_id = {
            identifier: token
            for identifier, token in zip(actionable_identifiers, generated_tokens.keys())
        }
        # Keep CSRF store aligned to the currently rendered actionable resources.
        session['csrf_tokens'] = dict(generated_tokens)

        return render_template(
            'cards.html',
            items=items,
            next_page=None,
            tokens_by_id=tokens_by_id,
            region=session['region'],
            search_query=search_query,
            default_search_query=default_search_query,
            initial_search_query=initial_search_query,
            query_mode=query_mode,
            show_query=is_initial_page,
            total_count=len(items),
        )

    # Cost update endpoint. Uses app-scoped signer for CostService.
    @app.route('/costs', methods=[HTTPMethod.GET])
    def costs() -> str:
        if not session.get('user'):
            raise exceptions.Unauthorized

        identifiers = list(dict.fromkeys([i for i in request.args.getlist('identifier') if i]))
        try:
            cost_map = ctx.cost_service.get_current_costs(ctx.cfg['tenancy'])
        except Exception:
            app.logger.exception('/costs failed to load costs, falling back to zeros')
            cost_map = {}

        cost_items = [
            {'identifier': identifier, 'current_cost': float(cost_map.get(identifier, 0.0) or 0.0)}
            for identifier in identifiers
        ]
        return render_template(
            'components/cost_updates.html',
            cost_items=cost_items,
            total_current_cost=sum(item['current_cost'] for item in cost_items),
        )

    # Cost Batch handling to return cost data as page is rendered on client. Uses
    # app-scoped signer for CostService.
    @app.route('/costs/batch', methods=[HTTPMethod.POST])
    def costs_batch():
        if not session.get('user'):
            raise exceptions.Unauthorized

        payload = request.get_json(silent=True) or {}
        identifiers = payload.get('identifiers') if isinstance(payload, dict) else None
        if not isinstance(identifiers, list):
            identifiers = request.form.getlist('identifier')
        identifiers = list(dict.fromkeys([str(i) for i in identifiers if i]))[:100]

        try:
            cost_map = ctx.cost_service.get_current_costs(ctx.cfg['tenancy'])
        except Exception:
            app.logger.exception('/costs/batch failed to load costs, falling back to zeros')
            cost_map = {}

        items = [
            {'identifier': identifier, 'current_cost': float(cost_map.get(identifier, 0.0) or 0.0)}
            for identifier in identifiers
        ]
        return jsonify({'items': items})
