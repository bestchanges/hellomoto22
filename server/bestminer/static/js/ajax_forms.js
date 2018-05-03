// form https://medium.com/@doobeh/posting-a-wtform-via-ajax-with-flask-b977782edeee
$(document).ready(function() {
    $('.ajax_form').submit(function (e) {
        var url = this.action; // send the form data here
        // TODO: disable form submit input until this request complete
        var form = this
        $.ajax({
            type: "POST",
            url: url,
            form: this,
            data: $('form').serialize(), // serializes the form's elements.
            success: function (data) {
                if (data.error) {
                    console.log(data)  // display the returned data in the console.
                    error_messages = []
                    for (var i in data.validation_errors) {
                        // alert(data.validation_errors[i]);
                        var message = data.validation_errors[i]
                        var search = $("label[for='" + i + "']");
                        if (search.length > 0) {
                            label = search[0];
                            console.log(label);
                            error_messages.push(label.innerText + ": " + message);
                        } else {
                            error_messages.push(i + ': ' + message);
                        }
                    }
                    alert(error_messages.join("\n"))
                } else {
                    alert(data)
                }
            },
            error: function (xhr, ajaxOptions, thrownError) {
                    console.log(xhr)  // display the returned data in the console.
                    // alert(xhr.status);
                    alert(thrownError);
            }
         });
        e.preventDefault(); // block the traditional submission of the form.
    });
    // Inject our CSRF token into our AJAX request.
    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            // TODO: support multiple CSRF tokens
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", "{{ form.csrf_token._value() }}")
            }
        }
    })
});
