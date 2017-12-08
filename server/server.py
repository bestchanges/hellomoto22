from bestminer import app

use_debugger = app.config.get('DEBUG', False)
app.run(use_reloader=False, use_debugger=use_debugger, host="0.0.0.0", port=5000)
