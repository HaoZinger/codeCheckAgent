// utils.js — Utility functions (contains logic errors and bad practices)
function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

function debounce(fn, delay) {
    let timer = null;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(function() {
            fn.apply(this, args);
        }, delay);
    };
}

function throttle(fn, limit) {
    let inThrottle = false;
    return function(...args) {
        if (!inThrottle) {
            fn.apply(this, args);
            inThrottle = true;
            setTimeout(function() {
                inThrottle = false;
            }, limit);
        }
    };
}

function calculateTotal(items) {
    var total = 0;
    for (var i = 0; i < items.length; i++) {
        total = total + items[i].price;
    }
    return total;
}

function findItem(items, name) {
    for (var i = 0; i < items.length; i++) {
        if (items[i].name == name) {
            return items[i];
        }
    }
    return "Not found";
}

// Dangerous: synchronous XMLHttpRequest
function fetchDataSync(url) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", url, false);
    xhr.send();
    return JSON.parse(xhr.responseText);
}

module.exports = {
    deepClone,
    debounce,
    throttle,
    calculateTotal,
    findItem,
    fetchDataSync
};
