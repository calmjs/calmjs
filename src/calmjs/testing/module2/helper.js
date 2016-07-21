'use strict';

var helper = require('calmjs/testing/module2/mod/helper');

var main = function () {
    console.log('module2 calling: ' + helper.help());
};

exports.main = main;
