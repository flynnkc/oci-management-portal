#!/usr/bin/python3.11

from flask import Flask, Response

from .config import Configuration
from .web.setup import initialize_service_context
from .web.routes import register_page_routes, register_action_routes


def add_handlers(app: Flask, config: Configuration, **kwargs) -> Flask:
    ctx = initialize_service_context(app, config)

    register_page_routes(app, ctx)
    register_action_routes(app, ctx)

    # Add standard headers for security
    @app.after_request
    def add_standard_headers(response: Response) -> Response:
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=()')
        return response

    return app
