$(function () {
    $(".widget_resizable").resizable({
        maxHeight: 400,
        minHeight: 400,
        minWidth: 306.89,
        handles: "w, e",
        containment: ".ul_sort"
    });
    $(".ul_sort").sortable({});
    $(".ul_sort").disableSelection();
    // $( ".pbar" ).progressbar({
    //   value: 50}).children("span").appendTo(this);
});

function add_widget() {
    var popup = document.getElementById("myPopup");
    popup.classList.toggle("show");
}

function delete_widget(printer_name) {
    $.post("/remove_widget", {'printer_name': printer_name}, function (data) {
        if (data['status'] === 'success') {
            location.reload()
        }
    })
}

function create_widget(printer_name, ip_address) {
    const regex = new RegExp(/^((\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5])\.){3}(\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5])$/gm);
    if (printer_name[0].value !== '' && regex.test(ip_address[0].value)) {
        $.post("/add_widget", {
            'printer_name': printer_name[0].value,
            'ip_address': ip_address[0].value
        }, function (data) {
            if (data['status'] === 'success') {
                location.reload()
            }
        })
    } else {
        console.log(regex.test(ip_address[0].value))
        console.log(ip_address[0].value)
        if (printer_name[0].value === '') {
            $('[name="printer_name"]').css('background-color', 'red')
        } else if (!(regex.test(ip_address[0].value))) {
            $('[name="ip_address"]').css('background-color', 'red')
        }
    }
}

function set_file_list(select_id, ip_address) {
    var select = document.getElementById(select_id);
    while (select.hasChildNodes()) {
        select.removeChild(select.firstChild);
    }
    $.post("/file_list", {'ip_address': ip_address}, function (data) {
        $.each(data, function () {
            var opt = document.createElement('option');
            opt.value = this.file;
            opt.innerHTML = this.file;
            select.appendChild(opt);
        })
    })
}

let ws = new WebSocket("ws://localhost:8000/ws");
ws.onmessage = function (event) {
    var data = JSON.parse(event.data);
    for (var d in data) {
        for (var i in data[d]) {
            var select_id = i;
            var val = data[d][i];
            var select = document.getElementById(select_id);
            while (select.hasChildNodes()) {
                select.removeChild(select.firstChild);
            }
            $.each(val, function () {
                var opt = document.createElement('option');
                opt.value = this;
                opt.innerHTML = this;
                select.appendChild(opt);
            })
        }
    }
};

//$("#ww3t_progressbar").progressbar({value: 75}).children("span").html("75%")
var ws_progress = new WebSocket("ws://localhost:8000/ws_progress");
ws_progress.onmessage = function (event) {
    var data = JSON.parse(event.data);
    for (var d in data) {
        if (data[d]['percent'] === "false") {
            $('#' + data[d]['id']).progressbar({value: false}).children("span").html(data[d]['text'])
        } else {
            $('#' + data[d]['id']).progressbar({value: data[d]['percent']}).children("span").html(data[d]['text'])
        }
    }
};

function sendMessage(data) {
    // var ws = new WebSocket("ws://localhost:8000/ws");
    // var input = document.getElementById("messageText")
    ws.send(JSON.stringify(data));
    // input.value = ''
    // event.preventDefault()
}