var csrfToken = document.currentScript.getAttribute('csrf_token');
var resetDeadlinesUrl = document.currentScript.getAttribute('reset_deadlines_url');
var wrapper = $('.reset-deadlines-banner-wrapper');
var banner = $("<div class='reset-deadlines-banner'></div>");
var text = $("<div class='reset-deadlines-text'></div>").text("It looks like you've missed some important deadlines. Reset your deadlines and get started today.");
var form = $("<form method='post'></form>").attr('action', resetDeadlinesUrl);
var token = $("<input type='hidden' id='csrf_token' name='csrfmiddlewaretoken'>").attr('value', csrfToken);
var button = $("<button class='reset-deadlines-button'></button>").text('Reset my deadlines');

banner.append(text);
banner.append(form);
form.append(token);
form.append(button);

wrapper.append(banner);
