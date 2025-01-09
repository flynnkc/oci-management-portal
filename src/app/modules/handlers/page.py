from fdk import response, context

def page(ctx: context.InvokeContext, **kwargs) -> response.Response:
    return response.Response(ctx,
                             headers={'Content-Type': 'text/html'},
                             response_data='<h1>Pass</h1>')