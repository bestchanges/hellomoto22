function ajax_call(url, data) {
    $.getJSON(url, data, function(result){
        if (result.error) {
            alert("Error: " + result.error)
            return
        }
        if (result.message) {
            alert(result.message)
        } else {
            alert('OK')
        }
    });
}