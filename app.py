import os
from flask import Flask, jsonify, render_template

from config import Config
from utils.file_manager import ensure_storage_dirs
from routes.main_routes import main_bp
from routes.editor_routes import editor_bp
from routes.conversion_routes import conversion_bp
from routes.utility_routes import utility_bp
from routes.ocr_routes import ocr_bp
from routes.chat_routes import chat_bp
from routes.intelligence_routes import intelligence_bp

def create_app(config_class=Config):
    """Application factory for DocuFlex."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize directory infrastructure
    ensure_storage_dirs()
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(editor_bp)
    app.register_blueprint(conversion_bp)
    app.register_blueprint(utility_bp)
    app.register_blueprint(ocr_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(intelligence_bp)
    
    # Global error handlers
    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({
            "error": "The uploaded file is too large. Maximum allowed file size is 64 MB."
        }), 413
        
    @app.errorhandler(404)
    def not_found_error(error):
        if app.request_class.is_json:
            return jsonify({"error": "Resource not found."}), 404
        return render_template("index.html"), 404
        
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            "error": "An internal server error occurred while processing the document."
        }), 500
        
    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("==================================================")
    print(f"[*] iLovePDF Pro platform starting at http://127.0.0.1:{port}")
    print("    Local document processing active. No cloud APIs.")
    print("==================================================")
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)
