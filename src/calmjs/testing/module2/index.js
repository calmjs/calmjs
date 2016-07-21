'use strict';

var helper = require('calmjs/testing/module2/helper');

var main = function () {
    console.log('The "index" module will be calling "helper" sibling module.');
    helper();
};

exports.main = main;
