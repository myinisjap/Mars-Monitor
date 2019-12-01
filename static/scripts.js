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
});

function add_widget() {
    var popup = document.getElementById("myPopup");
    popup.classList.toggle("show");
}

function set_file_list(select_id, ip_address) {
    var select = document.getElementById(select_id);
    while (select.hasChildNodes()) {
        select.removeChild(select.firstChild);
    }
    $.post("/file_list", {'ip_address': ip_address}, function (data) {
        console.log(data);
        $.each(data, function () {
            console.log(this.file);
            var opt = document.createElement('option');
            opt.value = this.file;
            opt.innerHTML = this.file;
            select.appendChild(opt);
        })
    })
}

var ws = new WebSocket("ws://localhost:8000/ws");
ws.onmessage = function (event) {
    // console.log(event.data);
    // console.log(JSON.parse(event.data));
    var data = JSON.parse(event.data);
    for (var d in data) {
        for (var i in data[d]) {
            console.log(i);
            console.log(data[d][i]);
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
// console.log(data.key);
//  $.each(data, function() {
//      console.log(this.key);
//      console.log(this.value)
//  })
// // var messages = document.getElementById('messages')
// var message = document.createElement('li')
// var content = document.createTextNode(event.data)
// message.appendChild(content)
// messages.appendChild(message)

function sendMessage(data) {
    // var ws = new WebSocket("ws://localhost:8000/ws");
    // var input = document.getElementById("messageText")
    ws.send(data);
    // input.value = ''
    // event.preventDefault()
}