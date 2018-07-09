"use strict";

require('css!calmjs/testing/module4/widget.css');

var textbox = function(name) {
    return '<input class="module4" name="' + name + '" value="" />';
}

exports.textbox = textbox;
