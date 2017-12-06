


# prepare data for work
app.add_url_rule('/client/rig_config', view_func=views.client_config1, methods=["GET", "POST", "PUT"])
app.add_url_rule('/client/stat_and_task', view_func=views.recieve_stat_and_return_task, methods=["GET", "POST", "PUT"])
app.add_url_rule('/client/stat', view_func=views.receive_stat, methods=["GET", "POST", "PUT"])
app.add_url_rule('/client/task', view_func=views.send_task, methods=["GET", "POST", "PUT"])

#app.add_url_rule('/promo', view_func=views.index)
#app.add_url_rule('/', view_func=views.index)
app.add_url_rule('/download_win', view_func=download_win)


app.add_url_rule('/configs', view_func=views.config_list, methods=["GET", "POST"])
app.add_url_rule('/configs.json', view_func=views.config_list_json)
app.add_url_rule('/config/', view_func=views.config_edit, defaults={'id': None}, methods=["GET", "POST"])
app.add_url_rule('/config/<id>', view_func=views.config_edit, methods=["GET", "POST"])


def main():
    # Start logging server to get output from the clients
    logging_server = LoggingServer()
    logging_server.start()

    initial_data.initial_data()
    initial_data.sample_data()
    initial_data.test_data()

    login_manager.init_app(app)

    profit_manager.start()
    rig_manager.distribute_all_rigs()

    # recreate client zip
    # commented as soon as run separately in update.sh
    # client_zip_windows_for_update()

    app.run(use_reloader=False, use_debugger=True, host="0.0.0.0", port=5000)



if __name__ == "__main__":
    main()
