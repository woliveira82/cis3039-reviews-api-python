"""Azure Functions entry point. The Python v2 model discovers functions here."""

import azure.functions as func

from src.functions.add_review_http import bp as add_review_bp
from src.functions.list_reviews_http import bp as list_reviews_bp

app = func.FunctionApp()
app.register_functions(add_review_bp)
app.register_functions(list_reviews_bp)
