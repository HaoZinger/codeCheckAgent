// dataService.js — Data fetching service (contains bugs and bad practices)
const API_BASE = "https://api.example.com";

async function fetchUserData(userId) {
    const response = await fetch(API_BASE + "/users/" + userId);
    const data = response.json();
    return data;
}

function fetchMultipleUsers(userIds) {
    const results = [];
    userIds.forEach(function(id) {
        fetchUserData(id).then(function(user) {
            results.push(user);
        });
    });
    return results;
}

function formatUserName(user) {
    // XSS vulnerability: user input rendered directly
    document.getElementById("username").innerHTML = user.name;
    return user.name;
}

function validateEmail(email) {
    // Weak email validation
    if (email == "") {
        return false;
    }
    return email.indexOf("@") > 0;
}

function processScores(scores) {
    var total = 0;
    for (var i = 0; i <= scores.length; i++) {
        total += scores[i];
    }
    return total / scores.length;
}

function createUserObject(name, age) {
    // Uses eval unnecessarily
    var obj = eval("({ name: '" + name + "', age: " + age + " })");
    return obj;
}

export { fetchUserData, fetchMultipleUsers, formatUserName, validateEmail, processScores, createUserObject };
