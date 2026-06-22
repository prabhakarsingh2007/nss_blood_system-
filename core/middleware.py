import traceback
from django.http import HttpResponse

class ExceptionTracebackMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        tb = traceback.format_exc()
        html = f"""
        <html>
        <head><title>Debug Traceback</title></head>
        <body style="font-family: monospace; background: #1e1e2e; color: #cdd6f4; padding: 20px; line-height: 1.5;">
            <div style="max-width: 1000px; margin: 0 auto; background: #313244; padding: 30px; border-radius: 12px; box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);">
                <h1 style="color: #f38ba8; margin-top: 0; border-bottom: 2px solid #f38ba8; padding-bottom: 10px;">Django Exception Caught</h1>
                <p><strong>Exception Type:</strong> <code style="background: #11111b; padding: 2px 6px; border-radius: 4px; color: #fab387;">{type(exception).__name__}</code></p>
                <p><strong>Message:</strong> <code style="background: #11111b; padding: 2px 6px; border-radius: 4px; color: #a6e3a1;">{str(exception)}</code></p>
                <h2 style="color: #89b4fa; margin-top: 20px;">Traceback:</h2>
                <pre style="background: #11111b; padding: 20px; border-radius: 8px; overflow-x: auto; color: #cdd6f4; font-size: 14px; border: 1px solid #45475a;">{tb}</pre>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html, status=500)
