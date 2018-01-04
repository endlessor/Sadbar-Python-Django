function clean_err ($form) {
    $.each($form.find('input[type="text"],' +
            'input[type="password"],'+
            'input[type="datetime"],'+
            'input[type="datetime-local"],'+
            'input[type="date"],'+
            'input[type="month"],'+
            'input[type="time"],'+
            'input[type="week"],'+
            'input[type="number"],'+
            'input[type="email "],'+
            'input[type="url"],'+
            'input[type="search"],'+
            'input[type="tel"],'+
            'input[type="color "],'+
            'select').parents('.col-md-9'), function(k, v) {
        $(v).find('span.err-block').remove();
        $(v).removeClass('has-error');
    })
}
function set_err (err_data) {
    $.each(err_data, function(key, val) {
        var $el = $('[name="'+key+'"]');
        $el.parents('.col-md-9').addClass('has-error');
        for(var i in val) {
            var $err_text = $("<span/>", {'class': 'help-block err-block', 'text': val[i].message});
            $el.parents('.col-md-9').append($err_text);
        }
    })
}

var showMessage = function(txt, css) {
    if (typeof css == "undefined") {
        var css = 'alert alert-success';
    }
    var hideMessage = function() {
        $message.fadeOut(1000);
    }
    var $message = $('<div/>', {class: css, html: txt});
    $('body').append($message);
    $message.fadeIn(1000);
    setTimeout(hideMessage, 3000);
}

function filter_apply(key, val) {
    if(val != -1) {
        if (window.location.href.indexOf(key+'=') > -1 ) {
            var regex = new RegExp(key+"=([\\w-\\.@]+)(?=\\&|\\?|\\#|$){1}");
            var nurl = window.location.href.replace(regex, key+"="+val);
            var nurl = nurl.replace(/(?:\?|\&)page=(\d+)/, '')
        } else {
            var delimiter = window.location.href.indexOf('?') == -1 ? '?' : '&'
            if (delimiter == '&') {
                if (window.location.href.indexOf('page=') == -1) {
                    var nurl = window.location.href + '&'+key+'='+val;
                } else if (window.location.href.indexOf('page=') != -1) {
                    var re = /page=(\d+)/
                    var nurl = window.location.href.replace(re, key+"="+val) ;
                }
            } else {
                var nurl = window.location.href + '?'+key+'='+val;
            }
        }
    } else {
        var regex = new RegExp("(?:\\?|\\&)"+key+"=([\\w-\\.@]+)(?=\\&|\\?|\\#|$){1}");
        var nurl = window.location.href.replace(regex, '');
        if (nurl.indexOf('?') == -1) {
            nurl = nurl.replace('&', '?');
        }
    }
    window.location.href = nurl;
}

function scrollToBottom(object) {
    $(object).scrollTop($(object)[0].scrollHeight);
}

function downloadAsTextFile(s) {
    function dataUrl(data) {
        return "data:x-application/text," + escape(data);
    }
    window.open(dataUrl(s));
}

$(function(){
    var storage = localStorage.getItem('steps');
    if(storage != "" && storage != null) {
        storage = JSON.parse(storage);
        if (storage.length > 0 && storage[0] == 'must_be_empty_for_now') {
            localStorage.setItem('steps', JSON.stringify('[]'));
        }
        if(window.location.href.match('list') && storage.length > 50) {
            localStorage.setItem('steps', JSON.stringify('[]'));
        }
    } else if(storage == null) {
        localStorage.setItem('steps', JSON.stringify('[]'));
    }

    $(".client_edit").submit(function(e) {
        e.preventDefault(); // avoid to execute the actual submit of the form.
        var $form = $(this);
        var steps = JSON.parse(localStorage.getItem('steps'));
        var step = steps[steps.length - 1];
        clean_err($form);
        $.ajax({
            type: "POST",
            url: $(".client_edit").attr('action'),
            data: $(".client_edit").serialize(), // serializes the form's elements.
            success: function(data)
            {
                try {
                    err_data = $.parseJSON(data)
                    set_err(err_data);
                    showMessage('The form contains errors.', 'alert alert-danger');
                } catch (err) {
                    showMessage('Client <strong>' + $('#id_name').val() + '</strong> was saved successfully!');
                        if (window.location.href.indexOf("/clients/add/") >= 0) {
                            window.location.href = "/clients/list/";
                        }
                }
            }
        });
    });

    $(".campaign_edit").submit(function(e) {
        e.preventDefault(); // avoid to execute the actual submit of the form.
        var $form = $(this);
        var steps = JSON.parse(localStorage.getItem('steps'));
        var step = steps[steps.length - 1];
        clean_err($form);
        $.ajax({
            type: "POST",
            url: $(".campaign_edit").attr('action'),
            data: $(".campaign_edit").serialize(), // serializes the form's elements.
            success: function(data)
            {
                try {
                    err_data = $.parseJSON(data)
                    set_err(err_data);
                    showMessage('The form contains errors.', 'alert alert-danger');
                } catch (err) {
                    if(document.referrer.match('clients/edit')) {
                        window.location.href = "/clients/edit/" + step.id;
                        steps.pop();
                        localStorage.setItem('steps', JSON.stringify(steps));
                    } else {
                        showMessage('Campaign <strong>' + $('#id_name').val() + '</strong> was saved successfully!');
                        if (window.location.href.indexOf("/campaigns/add/") >= 0) {
                            window.location.href = "/campaigns/list/";
                        }
                    }
                }
            }
        });
    });

    $(".engagement_edit #sub").on('click', function(e) {
        if($('#id_engagement_id').val() != '') {
            var is_edit = true;
        } else {
            var is_edit = false;
        }
        e.preventDefault();
        var $form = $(this).parents('form');
        var string = ($(".engagement_edit").serialize());
        var tgCount = 0;
        var $btn = $(this);
        $("input[name='target_lists']:checked").each(function(e) {
            var check = $(this);
            if(string.match("&target_lists=" + check.attr('value'))) {
                tgCount++;
                return true;
            }
            string += "&target_lists=" + check.attr('value');
            tgCount++;
        });
        if(tgCount == 0) {
            alert('You must check at least one target list');
            return false;
        }
        var steps = JSON.parse(localStorage.getItem('steps'));
        var step = steps[steps.length - 1];
        clean_err($form);
        var submissionURL = $(".engagement_edit").attr('action');
        $.ajax({
            type: "POST",
            url: $(".engagement_edit").attr('action'),
            data: string, // serializes the form's elements.
            success: function(data)
            {
                try {
                    err_data = $.parseJSON(data);
                    set_err(err_data);
                    showMessage('The form contains errors.', 'alert alert-danger');
                } catch (err) {
                    if (is_edit) {
                        if(document.referrer.match('campaigns/edit')) {
                            window.location.href = "/campaigns/edit/" + step.id;
                            steps.pop();
                            localStorage.setItem('steps', JSON.stringify(steps));
                        } else {
                            showMessage('Engagement <strong>' + $('#id_name').val() + '</strong> was saved successfully!');
                        }
                    } else {
                        if (submissionURL.indexOf('oauth') !== -1) {
                            window.location.href = "/oauth-engagements/edit/" + data.engagement_id + "/";
                        } else {
                            window.location.href = "/engagements/edit/" + data.engagement_id + "/";
                        }
                    }
                }
            }
        });
    });

    $(".schedule_edit").submit(function(e) {
        e.preventDefault(); // avoid to execute the actual submit of the form.
        var $form = $(this);
        var steps = JSON.parse(localStorage.getItem('steps'));
        var step = steps[steps.length - 1];
        clean_err($form);
        $.ajax({
            type: "POST",
            url: $(".schedule_edit").attr('action'),
            data: $(".schedule_edit").serialize(), // serializes the form's elements.
            success: function(data)
            {
                try {
                    err_data = $.parseJSON(data);
                    set_err(err_data);
                    showMessage('The form contains errors.', 'alert alert-danger');
                } catch (err) {
                    if(document.referrer.match('engagements/edit')) {
                        window.location.href = "/engagements/edit/" + step.id;
                        steps.pop();
                        localStorage.setItem('steps', JSON.stringify(steps));
                    } else {
                        showMessage('Schedule <strong>' + $('#id_name').val() + '</strong> was saved successfully!');
                        if (window.location.href.indexOf("/schedules/add/") >= 0) {
                            window.location.href = "/schedules/list/";
                        }
                    }
                }
            }
        });
    });

    $(".email_server_edit").submit(function(e) {
        e.preventDefault(); // avoid to execute the actual submit of the form.
        var $form = $(this);
        var steps = JSON.parse(localStorage.getItem('steps'));
        var step = steps[steps.length - 1];
        var data = $(".email_server_edit").serializeArray();
        send_data = {}
        $.each(data, function(k, v) {
            send_data[v.name] = v.value;
        })
        clean_err($form);
        $.ajax({
            type: "POST",
            url: $(".email_server_edit").attr('action'),
            data: send_data, // serializes the form's elements.
            success: function(data)
            {
                try {
                    err_data = $.parseJSON(data)
                    set_err(err_data);
                    showMessage('The form contains errors.', 'alert alert-danger');
                } catch (err) {
                    if(document.referrer.match('engagements/edit')) {
                        window.location.href = "/engagements/edit/" + step.id;
                        steps.pop();
                        localStorage.setItem('steps', JSON.stringify(steps));
                    } else {
                        showMessage('Email server <strong>' + $('#id_login').val() + '</strong> was saved successfully!');
                        if (window.location.href.indexOf("/email-servers/add/") >= 0) {
                            window.location.href = "/email-servers/list/";
                        }
                    }
                }
            }
        });
    });

    $(".email_template_edit").submit(function(e) {
        e.preventDefault(); // avoid to execute the actual submit of the form.
        var $form = $(this);
        var steps = JSON.parse(localStorage.getItem('steps'));
        var step = steps[steps.length - 1];
        var data = $(".email_template_edit").serializeArray();
        send_data = {}
        $.each(data, function(k, v) {
            send_data[v.name] = v.value;
        })
        if (typeof CKEDITOR != 'undefined')
            send_data.template = CKEDITOR.instances.id_template.getData();
        clean_err($form);
        $.ajax({
            type: "POST",
            url: $(".email_template_edit").attr('action'),
            data: send_data, // serializes the form's elements.
            success: function(data)
            {
                try {
                    err_data = $.parseJSON(data)
                    set_err(err_data);
                    showMessage('The form contains errors.', 'alert alert-danger');
                } catch (err) {
                    if(document.referrer.match('engagements/edit')) {
                        window.location.href = "/engagements/edit/" + step.id;
                        steps.pop();
                        localStorage.setItem('steps', JSON.stringify(steps));
                    } else {
                        showMessage('Email template <strong>' + $('#id_name').val() + '</strong> was saved successfully!');
                        if (window.location.href.indexOf("/email-templates/add/") >= 0) {
                            window.location.href = "/email-templates/list/";
                        }
                    }
                }
            }
        });
    });

    $(".redirect_page_edit").submit(function(e) {
        e.preventDefault(); // avoid to execute the actual submit of the form.
        var $form = $(this);
        var steps = JSON.parse(localStorage.getItem('steps'));
        var step = steps[steps.length - 1];

        var data = $(".redirect_page_edit").serializeArray();
        send_data = {}
        $.each(data, function(k, v) {
            send_data[v.name] = v.value;
        })
        if (typeof CKEDITOR != 'undefined')
            send_data.template = CKEDITOR.instances.template.getData();
        clean_err($form);
        $.ajax({
            type: "POST",
            url: $(".redirect_page_edit").attr('action'),
            data: send_data, // serializes the form's elements.
            success: function(data)
            {
                try {
                    err_data = $.parseJSON(data)
                    set_err(err_data);
                    showMessage('The form contains errors.', 'alert alert-danger');
                } catch (err) {
                    if(document.referrer.match('engagement/edit')) {
                        window.location.href = "/engagement/edit/" + step.id;
                        steps.pop();
                        localStorage.setItem('steps', JSON.stringify(steps));
                    } else {
                        showMessage('Redirect page <strong>' + $('#id_name').val() + '</strong> was saved successfully!');
                        if (window.location.href.indexOf("/redirect-pages/add/") >= 0) {
                            window.location.href = "/redirect-pages/list/";
                        }
                    }
                }
            }
        });
    });

    $(".landing_page_edit").submit(function(e) {
        e.preventDefault(); // avoid to execute the actual submit of the form.
        var $form = $(this);
        var steps = JSON.parse(localStorage.getItem('steps'));
        var step = steps[steps.length - 1];

        var data = $(".landing_page_edit").serializeArray();
        send_data = {}
        $.each(data, function(k, v) {
            send_data[v.name] = v.value;
        })
        if (typeof CKEDITOR != 'undefined')
            send_data.template = CKEDITOR.instances.template.getData();
        clean_err($form);
        $.ajax({
            type: "POST",
            url: $(".landing_page_edit").attr('action'),
            data: send_data, // serializes the form's elements.
            success: function(data)
            {
                try {
                    err_data = $.parseJSON(data)
                    set_err(err_data);
                    showMessage('The form contains errors.', 'alert alert-danger');
                } catch (err) {
                    if(document.referrer.match('engagement/edit')) {
                        window.location.href = "/engagement/edit/" + step.id;
                        steps.pop();
                        localStorage.setItem('steps', JSON.stringify(steps));
                    } else {
                        showMessage('Landing page <strong>' + $('#id_name').val() + '</strong> was saved successfully!');
                        if (window.location.href.indexOf("/landing_pages/add/") >= 0) {
                            window.location.href = "/landing_pages/list/";
                        }
                    }
                }
            }
        });
    });

    $(".phishing_domain_edit").submit(function(e) {
        e.preventDefault(); // avoid to execute the actual submit of the form.
        var $form = $(this);
        var steps = JSON.parse(localStorage.getItem('steps'));
        var step = steps[steps.length - 1];
        var data = $(".phishing_domain_edit").serializeArray();
        send_data = {}
        $.each(data, function(k, v) {
            send_data[v.name] = v.value;
        })
        clean_err($form);
        $.ajax({
            type: "POST",
            url: $(".phishing_domain_edit").attr('action'),
            data: send_data, // serializes the form's elements.
            success: function(data)
            {
                try {
                    err_data = $.parseJSON(data)
                    $.each(err_data, function(key, val) {
                        var $el = $('[name="domain_name"]');
                        $el.parents('.col-md-6').addClass('has-error');
                        for(var i in val) {
                            var $err_text = $("<span/>", {'class': 'help-block err-block', 'text': val[i].message});
                            $el.parents('.col-md-6').append($err_text);
                        }
                    });
                    showMessage('The form contains errors.', 'alert alert-danger');
                } catch (err) {
                    if(document.referrer.match('engagements/edit')) {
                        window.location.href = "/engagements/edit/" + step.id;
                        steps.pop();
                        localStorage.setItem('steps', JSON.stringify(steps));
                    } else {
                        showMessage('Phishing domain <strong>' + $('input[name="protocol"]:checked').val() + '://' + $('#id_domain_name').val() + '</strong> was saved successfully!');
                        if (window.location.href.indexOf("/phishing-domains/add/") >= 0) {
                            window.location.href = "/phishing-domains/list/";
                        }
                    }
                }
            }
        });
    });

    // Toggles visibility of help text on /landing-pages/edit/ based on
    // ScraperUserAgent selection:
    toggleScraperHelpText = function () {
        var $scraperSelectWidget = $('#id_scraper_user_agent');
        var $scraperHelpText = $scraperSelectWidget.parent().find('.help-block');
        if ($scraperSelectWidget.val() === "") {
            $scraperHelpText.hide();
        } else {
            $scraperHelpText.show();
        }
    }
    $('#id_scraper_user_agent').on('change', toggleScraperHelpText);
    toggleScraperHelpText();

    // Changes modal steps:
    sendEvent = function (sel, step) {
        $(sel).trigger('next.m.' + step);
    }

    // The modal being closed prevents the button inside it from being hidden
    // by JS triggered from #engagement_preview_button's onclick. (see below)
    $('#engagement_preview_button').on('click', function() {
        $previewButton = $(this);
        if ($previewButton.attr('data-is-oauth') === 'True') {
            var $previewEngagementModal = $('#preview_oauth_engagement_modal');
        } else {
            var $previewEngagementModal = $('#preview_engagement_modal');
        }

        $previewEngagementModal.attr('data-modal-preview-only', true);
        createEngagementPreviewModal($previewButton.attr('data-engagement'));
        $previewEngagementModal.modal('show');
    });

    // This toggles access to the final engagement confirmation screen via the
    // redirect preview step's "Confirm" button based on whether or not the
    // modal is in preview-only mode:
    $('#step_two_confirm').on('click', function() {
        var $engagementPreviewModal = $('#preview_engagement_modal');
        var $stepThreeConfirmButton = $('#step_three_confirm');

        if ($engagementPreviewModal.attr('data-modal-preview-only') === "true") {
            $stepThreeConfirmButton.attr('data-dismiss', 'modal');
            $stepThreeConfirmButton.attr('onclick', "sendEvent('#preview_engagement_modal', 1)");
        } else {
            $stepThreeConfirmButton.removeAttr('data-dismiss');
            $stepThreeConfirmButton.attr('onclick', "sendEvent('#preview_engagement_modal', 4)");
        }
    });

    // As above, but for the OAuth preview modal:
    $('#oauth_step_one_confirm').on('click', function() {
        var $stepOneConfirmButton = $(this);
        var $engagementPreviewModal = $('#preview_oauth_engagement_modal');

        if ($engagementPreviewModal.attr('data-modal-preview-only') === "true") {
            $stepOneConfirmButton.attr('data-dismiss', 'modal');
        } else {
            $stepOneConfirmButton.removeAttr('data-dismiss');
        }
    });

    function resetEngagementPreviewModal() {
        sendEvent('#preview_engagement_modal, #preview_oauth_engagement_modal', 1);
        // Take the modal out of preview-only mode:
        $('#preview_engagement_modal, #preview_oauth_engagement_modal').attr('data-modal-preview-only', "false");
    }

    // Everything to do when the modal is closed.
    $('#preview_engagement_modal, #preview_oauth_engagement_modal').on('hidden.bs.modal', function () {
        resetEngagementPreviewModal();
    });

    // Handles the behavior of the "Begin Engagement" button on the engagementEdit page's preview modal.
    $('#btn_begin_engagement, #btn_begin_oauth_engagement').on('click', function() {
        var $beginEngagementButton = $(this);
        var engagementId = $beginEngagementButton.attr('data-engagement');

        // Reference for the bit on the end: http://stackoverflow.com/a/15651670
        var $engagementControlButton = $('#current_engagements .engagement-control, #engagement_for_client .engagement-control, #engagements_list .engagement-control').filter(function() { return $(this).data('engagement') == engagementId; });
        var $span = $engagementControlButton.parents('tr').find('span.engagements-list-status-text');
        var $spanBadge = $engagementControlButton.parents('tr').find('span.badge');
        var engagementControlClasses = 'glyphicon-minus glyphicon-refresh glyphicon-pause glyphicon-remove glyphicon-ok btn-light-blue btn-light-green btn-grey btn-red btn-dark-green';

        var $engagementPreviewModal = $('#preview_engagement_modal, #preview_oauth_engagement_modal');
        $engagementPreviewModal.modal('hide');

        // Tell the server to begin the Engagement.
        $.ajax({
            url: '/schedule/start-stop-mail-send/',
            method: 'POST',
            data: {'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                   'engagement_id': engagementId}
        }).done(function(response) {
            // Swap icons and text as required by the new Engagement state.
            if (response.state === 0) {
                $engagementControlButton.removeClass(engagementControlClasses).addClass('glyphicon-minus btn-light-blue');
                $span.text('Not launched').removeClass('engagement-error-tag');
            } else if (response.state === 1) {
                $engagementControlButton.removeClass(engagementControlClasses).addClass('glyphicon-refresh btn-light-green');
                $span.text('In progress').removeClass('engagement-error-tag');
            } else if (response.state === 2) {
                $engagementControlButton.removeClass(engagementControlClasses).addClass('glyphicon-pause btn-grey');
                $span.text('Paused').removeClass('engagement-error-tag');
            } else if (response.state === 3) {
                $engagementControlButton.removeClass(engagementControlClasses).addClass('glyphicon-remove btn-red');
                $span.text('Error').addClass('engagement-error-tag');
            } else if (response.state === 4) {
                $engagementControlButton.removeClass(engagementControlClasses).addClass('glyphicon-ok btn-dark-green');
                $span.text('Completed').removeClass('engagement-error-tag');
            }
            $spanBadge.text(response.status_text);
        });

    });

    function createEngagementPreviewModal(engagementId) {
        $.ajax({
            url: '/engagements/preview-data/'+engagementId+'/',
            method: 'GET',
            data: {'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                   'engagement_id': engagementId}
        }).done(function(response) {
            // Using a conditional allows us to change only one modal in this
            // function. This is intended to cut down on iframe updates.
            if (response.is_oauth) {
                var $previewEngagementModal = $('#preview_oauth_engagement_modal');
            } else {
                var $previewEngagementModal = $('#preview_engagement_modal');
            }
            // Every span with user-visible data:
            $previewEngagementModal.find('.preview-data-engagement-name').text(response.engagement_name);
            $previewEngagementModal.find('.preview-data-engagement-schedule-name').text(response.engagement_schedule_name);
            $previewEngagementModal.find('.preview-data-target-list-names').text(response.target_list_names);
            $previewEngagementModal.find('.preview-data-total-target-count').text(response.total_target_count);
            $previewEngagementModal.find('.preview-data-from-email').text(response.from_email);
            $previewEngagementModal.find('.preview-data-subject').text(response.subject);
            $previewEngagementModal.find('.preview-data-first-ve-target-email').text(response.first_ve_target_email);
            $previewEngagementModal.find('.preview-data-first-ve-target-list').text(response.first_ve_target_list);
            $previewEngagementModal.find('.preview-data-first-ve-send-at').text(response.first_ve_send_at);
            $previewEngagementModal.find('.preview-data-first-ve-landing-page-type').text(response.first_ve_landing_page_type);
            $previewEngagementModal.find('.preview-data-first-ve-landing-page-name').text(response.first_ve_landing_page_name);
            $previewEngagementModal.find('.preview-data-first-ve-redirect-page-type').text(response.first_ve_redirect_page_type);
            $previewEngagementModal.find('.preview-data-first-ve-redirect-page-name').text(response.first_ve_redirect_page_name);
            if (response.first_ve_landing_page_type === "Manual") {
                $previewEngagementModal.find('.preview-data-first-ve-landing-page-url').text("N/A");
            } else {
                $previewEngagementModal.find('.preview-data-first-ve-landing-page-url').text(response.first_ve_landing_page_url);
            }
            if (response.first_ve_redirect_page_type === "Manual") {
                $previewEngagementModal.find('.preview-data-first-ve-redirect-page-url').text("N/A");
            } else {
                $previewEngagementModal.find('.preview-data-first-ve-redirect-page-url').text(response.first_ve_redirect_page_url);
            }
            if (response.missing_shortcodes.length > 0) {
                $previewEngagementModal.find('.preview-data-shortcodes-are-subset').html('<span>Email template shortcodes not found in all target lists:  </span><span style="font-weight: bold; color: red;">' + response.missing_shortcodes.join(", ") + '</span>');
            } else {
                $previewEngagementModal.find('.preview-data-shortcodes-are-subset').html('<span>There are no email template shortcodes not used by all target lists in this engagement.</span>');
            }

            // The left/right buttons:
            $previewEngagementModal.find('.engagement-preview-previous-target').attr('data-engagement', response.engagement_id);
            $previewEngagementModal.find('.engagement-preview-previous-target').attr('data-target', response.first_ve_target_id);
            $previewEngagementModal.find('.engagement-preview-next-target').attr('data-engagement', response.engagement_id);
            $previewEngagementModal.find('.engagement-preview-next-target').attr('data-target', response.first_ve_target_id);

            // All three iframes:
            $previewEngagementModal.find('#engagement-preview-email-template-iframe').attr('src', '/preview-engagement-email-template/'+response.engagement_id+'/'+response.first_ve_target_id+'/');
            $previewEngagementModal.find('#engagement-preview-landing-page-iframe').attr('src', '/landing-pages/preview/'+response.first_ve_landing_page_id+'/'+response.engagement_id+'/'+response.first_ve_target_id);  // no slash on the end, according to urls.py
            if (response.first_ve_redirect_page_type === 'URL') {
                $previewEngagementModal.find('#engagement-preview-redirect-page-iframe').attr('src', response.first_ve_redirect_page_url);
            } else {
                $previewEngagementModal.find('#engagement-preview-redirect-page-iframe').attr('src', '/landing-pages/preview/'+response.first_ve_redirect_page_id+'/'+response.engagement_id+'/'+response.first_ve_target_id);
            }

            // "Begin Engagement" button:
            $previewEngagementModal.find('#btn_begin_engagement, #btn_begin_oauth_engagement').attr('data-engagement', response.engagement_id);
        });
    }

    $('#current_engagements .engagement-control, #engagement_for_client .engagement-control, #engagements_list .engagement-control').on('click', function() {
        var $btn = $(this);
        var confirm1 = false;
        if ($btn.attr('data-is-oauth') === 'True') {
            var $engagementPreviewModal = $('#preview_oauth_engagement_modal');
        } else {
            var $engagementPreviewModal = $('#preview_engagement_modal');
        }
        var engagementControlClasses = 'glyphicon-minus glyphicon-refresh glyphicon-pause glyphicon-remove glyphicon-ok btn-light-blue btn-light-green btn-grey btn-red btn-dark-green';
        var engagementId = $(this).attr('data-engagement');

        if($btn.is('.glyphicon-minus')) {
            resetEngagementPreviewModal();
            createEngagementPreviewModal(engagementId);
            $engagementPreviewModal.modal('show');
        } else if ($btn.is('.glyphicon-refresh')) {
            confirm1 = confirm("This engagement is currently in progress. Are you sure that you want to pause it?");
        } else if ($btn.is('.glyphicon-pause')) {
            resetEngagementPreviewModal();
            createEngagementPreviewModal(engagementId);
            $engagementPreviewModal.modal('show');
        } else if ($btn.is('.glyphicon-remove')) {
            resetEngagementPreviewModal();
            createEngagementPreviewModal(engagementId);
            $engagementPreviewModal.modal('show');
        } else if ($btn.is('.glyphicon-ok')) {
            resetEngagementPreviewModal();
            createEngagementPreviewModal(engagementId);
            $engagementPreviewModal.modal('show');
        }

        if (confirm1) {
            $.ajax({
                url: '/schedule/start-stop-mail-send/',
                method: 'POST',
                data: {'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                       'engagement_id': engagementId}
            }).done(function(response) {
                if (response.state === 0) {
                    $btn.removeClass(engagementControlClasses).addClass('glyphicon-minus btn-light-blue');
                    $span.text('Not launched').removeClass('engagement-error-tag');
                } else if (response.state === 1) {
                    $btn.removeClass(engagementControlClasses).addClass('glyphicon-refresh btn-light-green');
                    $span.text('In progress').removeClass('engagement-error-tag');
                } else if (response.state === 2) {
                    $btn.removeClass(engagementControlClasses).addClass('glyphicon-pause btn-grey');
                    $span.text('Paused').removeClass('engagement-error-tag');
                } else if (response.state === 3) {
                    $btn.removeClass(engagementControlClasses).addClass('glyphicon-remove btn-red');
                    $span.text('Error').addClass('engagement-error-tag');
                } else if (response.state === 4) {
                    $btn.removeClass(engagementControlClasses).addClass('glyphicon-ok btn-dark-green');
                    $span.text('Completed').removeClass('engagement-error-tag');
                }
                $btn.parents('tr').find('span.badge').text(response.status_text);
            });
        }
    });

    $('#current_clients .glyphicon-play, #current_clients .glyphicon-pause').on('click', function() {
        var $btn = $(this);
        var confirm1;
        if($btn.is('.glyphicon-play')) {
            confirm1 = confirm("Are you sure that you want to play this campaign?");
        } else {
            confirm1 = confirm("Are you sure that you want to pause this campaign?");
        }
        if(confirm1) {
            $.ajax({
                url: '/schedule/start-stop-campaign/',
                method: 'POST',
                data: {'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                    'campaign_id': $(this).data('campaign'),
                    'action': $btn.data('action')}
            }).done(function(response) {
                if (response.status) {
                    $btn.data('action', 'false');
                    $btn.removeClass('glyphicon-play').addClass('glyphicon-pause');
                } else {
                    $btn.data('action', 'true');
                    $btn.removeClass('glyphicon-pause').addClass('glyphicon-play');
                }
                $btn.parents('tr').find('span.badge').text(response.status_text)
            });
        }
    });

    $('#decode-quo-pri').on('click', function () {
        send_data = {}
        if (typeof CKEDITOR != 'undefined')
            send_data.template = CKEDITOR.instances.id_template.getData();
        $.ajax({
            type: "POST",
            url: "/email-templates/decode-quopri/",
            data: send_data,
            success: function(data)
            {
                decoded_template = data.template;
                CKEDITOR.instances['id_template'].setData(decoded_template);
                if (data.error === 'not-quopri') {
                    showMessage('The template was not successfully Quoted Printable-decoded. This may mean the email was not Quoted Printable encoded and is already correct. ', 'alert alert-danger');
                } else if (data.error === 'internal') {
                    showMessage('The template was not successfully Quoted Printable-decoded due to an unknown internal error.', 'alert alert-danger');
                } else if (data.error === null) {
                    showMessage('Template decoding completed with no errors. If the rendered template view did not update, click Save, then reload this template in edit mode.');
                }
            }
        });
    });

    $('#check_landing_page_form').on('click', function () {
        $checkFormIcon = $('#check_landing_page_form_icon');
        toggleClasses = 'glyphicon-remove glyphicon-ok btn-danger btn-success'
        send_data = {}
        if (typeof CKEDITOR != 'undefined')
            send_data.template = CKEDITOR.instances.template.getData();
        $.ajax({
            type: "POST",
            url: "/landing-pages/check-form/",
            data: send_data,
            success: function(data)
            {
                if (data.success) {
                    showMessage('Landing page form found.');
                    $checkFormIcon.removeClass(toggleClasses).addClass('glyphicon-ok btn-success');
                    $checkFormIcon.fadeIn(300).delay(4000).fadeOut(2000);
                } else {
                    showMessage('Landing page form not found.', 'alert alert-danger');
                    $checkFormIcon.removeClass(toggleClasses).addClass('glyphicon-remove btn-danger');
                    $checkFormIcon.fadeIn(300).delay(4000).fadeOut(2000);
                }
            }
        });
    });

    $('div.submit_block').on('click', '#del', function (e) {
        if (!confirm("Are you sure?")) {
            e.preventDefault();
        }
    });

    $('.remove_element').on('click', function () {
        var $btn = $(this);
        var confirm1 = confirm("Are you sure?");
        if(confirm1) {
            $.ajax({
                url: '/' + $btn.data('url') + '/delete/' + $btn.data('id') + '/',
                method: 'POST',
                data: {
                    'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val()
                }
            }).done(function (response) {
                if (response.success) {
                    $btn.closest('tr').remove();
                }
            })
        }
    });

    $('#refetch').on('click', function() {
        if (confirm('Are You sure?')){
            var $form = $(this).parents('form')
            $form.append($("<input>", {type: 'hidden',
                                       name: 'refetch',
                                       value: true}));

            $form.submit();
        }
    });

    $('#landing-page-table .glyphicon-camera').on('click', function() {
        var landing_page_id = $(this).data('landing_id');
        window.open('/landing-pages/preview/'+ landing_page_id +'/',
            '', 'width=1200, height=700, scrollbars=1');
    });
    $('#landing-page-table .glyphicon-link').on('click', function() {
        var landing_page_link = $(this).data('landing_link');
        window.open(landing_page_link,
            '', 'width=1200, height=700, scrollbars=1');
    });

    // Hide the "Check Form" button if a 'url'-type LandingPage is loaded first.
    if ($('#id_page_type').val() == 'url') {
        $('#check_landing_page_form').hide();
    }

    $('#id_page_type').on('change', function() {
        $('#template').parents('.form-group').hide();
        $('#id_url').parents('.form-group').show();
        $('#id_scraper_user_agent').parents('.form-group').show();
        $('#refetch').hide();
        $('#check_landing_page_form').hide();
        $('#check_landing_page_form_icon').hide();
        if ($(this).val() == 'manual') {
            $('#id_scraper_user_agent').parents('.form-group').hide();
            $('#id_url').parents('.form-group').hide();
            $('#template').parents('.form-group').show();
            $('#check_landing_page_form').show();
            if(typeof CKEDITOR != 'undefined' && typeof CKEDITOR.instances.template == 'undefined') {
                CKEDITOR.replace('template', {
                    customConfig: '/static/ckeditor/ck-settings.js'
                });
            }
            $('#refetch').hide()
        } else if ($(this).val() == 'page' && is_source == true) {
            $('#id_scraper_user_agent').parents('.form-group').show();
            $('#id_url').parents('.form-group').show();
            $('#template').parents('.form-group').show();
            $('#check_landing_page_form').show();
            if(typeof CKEDITOR != 'undefined' && typeof CKEDITOR.instances.template == 'undefined') {
                CKEDITOR.replace('template', {
                    customConfig: '/static/ckeditor/ck-settings.js'
                });
            }
            $('#refetch').show()
        }
    });

    $('#filter_target').on('change', function (){
        filter_apply('filter_target', $(this).val())
    });

    $('#filter_status').on('change', function (){
        if ($(this).val() == 0) {
            filter_apply('filter_status', "0")
        } else {
            filter_apply('filter_status', $(this).val())
        }
    });

    $('#pg_size').on('change', function (){
        filter_apply('pg_size', $(this).val())
    });

    function bindPlusCreating(create_selector, path) {
        $(create_selector).on('click', function () {
            var win = window.open('/' + path + '/add/', '', 'width=830, height=600');
            var $select = $(this).closest('div.input-group').find('select');

            $(win).load(function () {
                $(win.document).contents().find('#campaign_edit').on('submit', function (e) {
                    e.preventDefault();

                    var data = {csrfmiddlewaretoken: $('input[name="csrfmiddlewaretoken"]').val()};
                    $(this).find(':input').each(function () {
                        data[this.name] = $(this).val();
                    });

                    $.ajax({
                        url: '/' + path + '/addajax/',
                        method: 'POST',
                        data: data
                    }).done(function (res) {
                        win.close();
                        $select.append($('<option/>', {
                            selected: 'selected',
                            value: res.id,
                            text: res.name
                        })).val(res.id);
                    })
                });
            })
        });
    }

    bindPlusCreating('#create_schedule', 'schedules');
    bindPlusCreating('#create_landing_page', 'landing-pages');

    function checkSheduleRadioBtn(val) {
        if(val == "now") {
            $("#column_start_sending_at").append($("#start_sending_at_picker").remove());
            $("#start_sending_at_form_group").css("display", "none");
        } else if(val == "after_time") {
            $("#column_start_sending_at").append($("#start_sending_at_picker").remove());
            $("#start_sending_at_form_group").css("display", "block")
            $('#start_sending_at_picker').datetimepicker({format: "HH:mm:ss"});
        } else if(val == "specific_time") {
            $("#column_start_sending_at").append($("#start_sending_at_picker").remove());
            $("#start_sending_at_form_group").css("display", "block");
            $('#start_sending_at_picker').datetimepicker({format: "YYYY-MM-DD HH:mm:ss"});
        }
    }
    checkSheduleRadioBtn($( "input[name='start_sending']:checked" ).val());

    $("input[name='start_sending']").on("click", function() {
        checkSheduleRadioBtn($( "input[name='start_sending']:checked" ).val());
    });

    function enableTimePickers() {
        $("#interval_picker").datetimepicker({format: "HH:mm:ss"});
    }
    if ($("#interval_picker").length){
        enableTimePickers();
    }

    function returnToStep () {
        var steps = JSON.parse(localStorage.getItem('steps'));
        if (steps == null || steps.length == 0) {
            return false;
        }
        var step = steps[steps.length - 1];

        if (window.location.href.match('engagements/add') && document.referrer.match('campaigns/edit')) {
            $('select[name="campaign"]').val(step.id);
        }
        if (window.location.href.match('campaigns/add') && document.referrer.match('clients/edit')) {
            $('select[name="client"]').val(step.id);
        }

    }
    returnToStep();

    (function checkEngagementState() {
        var delay = 2000;
        var isActive = true;

        // for campaign/edit page
        var $table = $('#current_engagements').find('table');
        if ($table.length) {

            var url = '/engagements/check-status/';
            var ids = $.map($table.find('td[data-id]'), function (e) {
                return $(e).data('id');
            });

            (function checkItems() {
                $.ajax({
                    url: url,
                    method: 'POST',
                    data: {
                        'ids': ids
                    }
                }).done(function (response) {
                    if (!response.error) {
                        var engagementControlClasses = 'glyphicon-minus glyphicon-refresh glyphicon-pause glyphicon-remove glyphicon-ok btn-light-blue btn-light-green btn-grey btn-red btn-dark-green';
                        response.forEach(function (k) {
                            var $table = $('#current_engagements').find('table');
                            var $row = $table.find('td[data-id="' + k['id'] + '"]').parent();
                            var $btn = $row.first('td').find('.engagement-control');
                            var $span = $row.find('span.campaigns-edit-status-text');
                            var $stats = $row.find('.result-statistics');

                            var total = k['statistics'][0]
                            var opened_total = k['statistics'][1][0]
                            var opened_ratio = k['statistics'][1][1]
                            var clicked_total = k['statistics'][2][0]
                            var clicked_ratio = k['statistics'][2][1]
                            var submitted_total = k['statistics'][3][0]
                            var submitted_ratio = k['statistics'][3][1]

                            if (k['status'][0] === 0) {
                                $btn.removeClass(engagementControlClasses).addClass('glyphicon-minus btn-light-blue');
                                $span.text('Not launched').qtip('destroy', true).attr('title', 'Not launched').removeClass('engagement-error-tag');
                            } else if (k['status'][0] === 1) {
                                $btn.removeClass(engagementControlClasses).addClass('glyphicon-refresh btn-light-green');
                                $span.text('In progress').qtip('destroy', true).attr('title', 'In progress').removeClass('engagement-error-tag');
                            } else if (k['status'][0] === 2) {
                                $btn.removeClass(engagementControlClasses).addClass('glyphicon-pause btn-grey');
                                $span.text('Paused').qtip('destroy', true).attr('title', 'Paused').removeClass('engagement-error-tag');
                            } else if (k['status'][0] === 3) {
                                $btn.removeClass(engagementControlClasses).addClass('glyphicon-remove btn-red');
                                $span.text('Error ' + k['status'][2][0]).attr('title', k['status'][2][1]).addClass('engagement-error-tag');
                                if ($span[0].hasAttribute('data-hasqtip')) {
                                    $span.qtip('enable');
                                } else {
                                    applyQtip($span);
                                }
                            } else if (k['status'][0] === 4) {
                                $btn.removeClass(engagementControlClasses).addClass('glyphicon-ok btn-dark-green');
                                $span.text('Completed').qtip('destroy', true).attr('title', 'Completed').removeClass('engagement-error-tag');
                            }
                            $table.find('td[data-id="' + k['id'] + '"] span.badge').text(k['status'][1]);

                            $stats.find('span.opened-stats').text(opened_ratio + ' Opened (' + opened_total + ' / ' + total + ')');
                            $stats.find('span.clicked-stats').text(clicked_ratio + ' Clicked (' + clicked_total + ' / ' + total + ')');
                            $stats.find('span.submitted-stats').text(submitted_ratio + ' Submitted (' + submitted_total + ' / ' + total + ')');
                        });
                    }
                    if (isActive) {
                        setTimeout(checkItems, delay);
                    }
                });
            })();
        }

        // for client/edit page
        var $table_clients = $('#current_clients').find('table');
        if ($table_clients.length) {
            url = '/engagements/check-status-campaign/';
            ids = $.map($table_clients.find('button[data-campaign]'), function (e) {
                return $(e).data('campaign');
            });

            (function checkItems() {
                $.ajax({
                    url: url,
                    method: 'POST',
                    data: {
                        'ids': ids
                    }
                }).done(function (response) {
                    if (!response.error) {
                        response.forEach(function (k) {
                            if (k['status'][0]) {
                                $table_clients.find('button[data-campaign="' + k['id'] + '"]').removeClass('glyphicon-play').addClass('glyphicon-pause');
                            } else {
                                $table_clients.find('button[data-campaign="' + k['id'] + '"]').removeClass('glyphicon-pause').addClass('glyphicon-play');
                            }
                            $table_clients.find('button[data-campaign="' + k['id'] + '"]').closest('tr').find('span.badge').text(k['status'][1])
                        });
                    }
                    if (isActive) {
                        setTimeout(checkItems, delay);
                    }
                });
            })();
        }

        // for engagements/list page
        var $table = $('#engagements_list').parents('table');
        if ($table.length) {

            var url = '/engagements/check-status/';
            var ids = $.map($table.find('tr[data-id]'), function (e) {
                return $(e).data('id');
            });

            (function checkItems() {
                $.ajax({
                    url: url,
                    method: 'POST',
                    data: {
                        'ids': ids
                    }
                }).done(function (response) {
                    if (!response.error) {
                        var engagementControlClasses = 'glyphicon-minus glyphicon-refresh glyphicon-pause glyphicon-remove glyphicon-ok btn-light-blue btn-light-green btn-grey btn-red btn-dark-green';
                        response.forEach(function (k) {
                            var $row = $table.find('tr[data-id="' + k['id'] + '"]');
                            var $btn = $row.first('td').find('.engagement-control');
                            var $span = $row.find('span.engagements-list-status-text');
                            var $stats = $row.find('.result-statistics');

                            var total = k['statistics'][0]
                            var opened_total = k['statistics'][1][0]
                            var opened_ratio = k['statistics'][1][1]
                            var clicked_total = k['statistics'][2][0]
                            var clicked_ratio = k['statistics'][2][1]
                            var submitted_total = k['statistics'][3][0]
                            var submitted_ratio = k['statistics'][3][1]

                            if (k['status'][0] === 0) {
                                $btn.removeClass(engagementControlClasses).addClass('glyphicon-minus btn-light-blue');
                                $span.text('Not launched').qtip('destroy', true).attr('title', 'Not launched').removeClass('engagement-error-tag');
                            } else if (k['status'][0] === 1) {
                                $btn.removeClass(engagementControlClasses).addClass('glyphicon-refresh btn-light-green');
                                $span.text('In progress').qtip('destroy', true).attr('title', 'In progress').removeClass('engagement-error-tag');
                            } else if (k['status'][0] === 2) {
                                $btn.removeClass(engagementControlClasses).addClass('glyphicon-pause btn-grey');
                                $span.text('Paused').qtip('destroy', true).attr('title', 'Paused').removeClass('engagement-error-tag');
                            } else if (k['status'][0] === 3) {
                                $btn.removeClass(engagementControlClasses).addClass('glyphicon-remove btn-red');
                                $span.text('Error ' + k['status'][2][0]).attr('title', k['status'][2][1]).addClass('engagement-error-tag');
                                if ($span[0].hasAttribute('data-hasqtip')) {
                                    $span.qtip('enable');
                                } else {
                                    applyQtip($span);
                                }
                            } else if (k['status'][0] === 4) {
                                $btn.removeClass(engagementControlClasses).addClass('glyphicon-ok btn-dark-green');
                                $span.text('Completed').qtip('destroy', true).attr('title', 'Completed').removeClass('engagement-error-tag');
                            }

                            $stats.find('span.opened-stats').text(opened_ratio + ' Opened (' + opened_total + ' / ' + total + ')');
                            $stats.find('span.clicked-stats').text(clicked_ratio + ' Clicked (' + clicked_total + ' / ' + total + ')');
                            $stats.find('span.submitted-stats').text(submitted_ratio + ' Submitted (' + submitted_total + ' / ' + total + ')');
                        });
                    }
                    if (isActive) {
                        setTimeout(checkItems, delay);
                    }
                });
            })();
        }
    })();

    // Updates Engagement state for the editEngagement main toggle button only.
    (function checkEngagementPage() {
        var isActive = true;
        var url = '/engagements/check-status/';
        var delay = 1000;
        $btn = $('#engagement_for_client .engagement-control');
        $span = $('#engagement_for_client .engagements-edit-status-text');
        var ids = [$('#id_engagement_id').val()];

        if ($btn.length) {
            (function checkItems() {
                $.ajax({
                    url: url,
                    method: 'POST',
                    data: {
                        'ids': ids
                    }
                }).done(function (response) {
                    if (!response.error) {
                        var engagementControlClasses = 'glyphicon-minus glyphicon-refresh glyphicon-pause glyphicon-remove glyphicon-ok btn-light-blue btn-light-green btn-grey btn-red btn-dark-green';
                        if (response[0].status[0] === 0) {
                            $btn.removeClass(engagementControlClasses).addClass('glyphicon-minus btn-light-blue');
                            $span.text('Not launched').qtip('destroy', true).attr('title', 'Not launched').removeClass('engagement-error-tag');
                        } else if (response[0].status[0] === 1) {
                            $btn.removeClass(engagementControlClasses).addClass('glyphicon-refresh btn-light-green');
                            $span.text('In progress').qtip('destroy', true).attr('title', 'In progress').removeClass('engagement-error-tag');
                        } else if (response[0].status[0] === 2) {
                            $btn.removeClass(engagementControlClasses).addClass('glyphicon-pause btn-grey');
                            $span.text('Paused').qtip('destroy', true).attr('title', 'Paused').removeClass('engagement-error-tag');
                        } else if (response[0].status[0] === 3) {
                            $btn.removeClass(engagementControlClasses).addClass('glyphicon-remove btn-red');
                            $span.text('Error ' + response[0].status[2][0]).attr('title', response[0].status[2][1]).addClass('engagement-error-tag');
                            if ($span[0].hasAttribute('data-hasqtip')) {
                                $span.qtip('enable');
                            } else {
                                applyQtip($span);
                            }
                        } else if (response[0].status[0] === 4) {
                            $btn.removeClass(engagementControlClasses).addClass('glyphicon-ok btn-dark-green');
                            $span.text('Completed').qtip('destroy', true).attr('title', 'Completed').removeClass('engagement-error-tag');
                        }
                    }
                    if (isActive) {
                        setTimeout(checkItems, delay);
                    }
                });
            })();
        }
    })();

    (function checkLandingPagePath() {
        var table = $('#landing-page-table');

        if (table.length) {
            var url = '/landing-pages/check-state/';
            var isActive = true;
            var delay = 1000;

            var ids = $.map(table.find('td[data-id]'), function (e) {
                return $(e).data('id');
            });

            (function sendIds() {
                $.ajax({
                    url: url,
                    method: 'POST',
                    data: {
                        'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                        'ids': ids
                    }
                }).done(function (response) {
                    if (!response.error) {
                        response.forEach(function (k) {
                            if (k[2] == 1) {
                                table.find('td[data-id="' + k[0] + '"] span').removeClass('glyphicon-remove glyphicon-refresh glyphicon-refresh-animate').addClass('glyphicon-ok');
                                table.find('td[data-id="' + k[0] + '"]').parent().find('.glyphicon-camera').removeClass('invisible');
                            } else if (k[2] == 2){
                                table.find('td[data-id="' + k[0] + '"] span').removeClass('glyphicon-ok glyphicon-remove').addClass('glyphicon-refresh glyphicon-refresh-animate');
                                table.find('td[data-id="' + k[0] + '"]').parent().find('.glyphicon-camera').addClass('invisible');
                            } else if (k[2] == 3){
                                table.find('td[data-id="' + k[0] + '"] span').removeClass('glyphicon-ok glyphicon-refresh glyphicon-refresh-animate').addClass('glyphicon-remove');
                                table.find('td[data-id="' + k[0] + '"]').parent().find('.glyphicon-camera').addClass('invisible');
                            }
                        });
                    }
                    if (isActive) {
                        setTimeout(sendIds, delay);
                    }
                });
            })();
        }
    })();

    if(window.location.pathname == "/targets-list/list/") {
        $('[data-target-description]').each(function(key, obj) {
            obj.textContent = decodeURI(obj.textContent);
        });
    }

    $('#check_email').on('click', function(){
        var $check_btn = $(this);
        $(this).prepend($('<span/>', {'class': 'glyphicon glyphicon-refresh glyphicon-refresh-animate'}))
        $.ajax({
            url: '/email-servers/test/',
            method: 'POST',
            data: {
                'host': $('form #id_host').val(),
                'port': $('form #id_port').val(),
                'login': $('form #id_login').val(),
                'email_pw': $('form #id_email_pw').val(),
                'use_tls': $('form #id_use_tls').prop('checked'),
                'test_recipient': $('form #id_test_recipient').val()
            }
        }).done(function (response) {
            if (response.success) {
                $('#check_email_status').attr('class', 'text-success');
            } else {
                $('#check_email_status').attr('class', 'text-danger');
            }
            $check_btn.find('span').remove();
            $('#check_email_status').text(response.message)
        });
    });

    $('#check_domain').on('click', function(){
        var $check_btn = $(this);
        $(this).prepend($('<span/>', {'class': 'glyphicon glyphicon-refresh glyphicon-refresh-animate'}))
        $.ajax({
            url: '/phishing-domains/test/',
            method: 'POST',
            data: {
                'protocol': $('input[name="protocol"]:checked').val(),
                'domain_name': $('form #id_domain_name').val()
            }
        }).done(function (response) {
            if (response.success) {
                $('#check_domain_status').attr('class', 'text-success');
            } else {
                $('#check_domain_status').attr('class', 'text-danger');
            }
            $check_btn.find('span').remove();
            $('#check_domain_status').text(response.message)
        });
    });

    $('#id_campaign').on('change', function() {
        loadTargetList($(this).val());
    })

    if($('#id_campaign') && $('#id_campaign').val()) {
        loadTargetList($('#id_campaign').val());
    }

    if($('#target_listst > div.col-md-9').height() > 410) {
        $('#target_listst > div.col-md-9').attr('style', 'height: 410px')
    }
    $('#filter_client').on('change', function(){
        filter_apply('client', $(this).val());
    })
    $('#preview_email').on('click', function() {
        var email_preview_window = window.open("", "MsgPreview", "width=800, height=700, scrollbars=1");
        if (typeof CKEDITOR != 'undefined')
            email_preview_window.document.write(CKEDITOR.instances.id_template.getData());
    })

    $('#email_templates_table .glyphicon-envelope').on('click', function() {
        $.ajax({
            url: '/email-templates/preview/' + $(this).data('id'),
            method: 'GET',
        }).done(function (response) {
            if (response.success) {
                var email_preview_window = window.open("", "MsgPreview", "width=800, height=700, scrollbars=1");
                email_preview_window.document.write(response.template);
            }
        });
    })

    if($('#id_target_lists').height() > 420) {
        $('#id_target_lists').height(420);
    } else {
        $('#id_target_lists').height('auto');
    }

    // Gmail API console

    function resetGmailListPage() {
        var $nextPageButton = $('#gmail_messages_next_page_btn');
        var $nextPageTokenStorage = $('#next_page_token');

        $nextPageButton.text('First Page');
        $nextPageTokenStorage.val('');
    }

    function gmailMessagesList(pageToken, maxResults, searchQuery) {
        var oAResultId = $('#oa_result_id').val();
        var $apiConsole = $('#google_api_console_widget');
        var $nextPageTokenStorage = $('#next_page_token');
        var $nextPageButton = $('#gmail_messages_next_page_btn');

        scrollToBottom($apiConsole);

        $.ajax({
            url: '/oauth-apis/google/gmail/messages/list/' + oAResultId + '/',
            method: 'POST',
            data: {
                'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                'maxResults': maxResults,
                'pageToken': pageToken,
                'searchQuery': searchQuery
            }
        }).done(function (response) {
            if (response.data) {

                $apiConsole.append('   ' + response.data.length + ' results.\n\n');

                for (i = 0; i < response.data.length; i++) {
                    $apiConsole.append('   email ID: ' + response.data[i].id + '\n');
                }
                if (response.nextPageToken === '') {
                    $apiConsole.append('\n  No next page token.\n');
                    $nextPageTokenStorage.val('');
                    resetGmailListPage();
                } else {
                    $apiConsole.append('\n  Next page token: ' + response.nextPageToken + '\n');
                    $nextPageTokenStorage.val(response.nextPageToken);
                    $nextPageButton.text('Next Page');
                }
                scrollToBottom($apiConsole);
            } else {
                $apiConsole.append('\n\n    There was an error.\n' + response.error + '\n');
                scrollToBottom($apiConsole);
            }
        }).fail(function (response) {
            $apiConsole.append('\n\n    There was an error.\n');
            scrollToBottom($apiConsole);
        });
    }

    function gmailDetailedList(pageToken, maxResults, searchQuery) {
        var oAResultId = $('#oa_result_id').val();
        var $apiConsole = $('#google_api_console_widget');
        var $nextPageTokenStorage = $('#next_page_token');
        var $nextPageButton = $('#gmail_messages_next_page_btn');

        scrollToBottom($apiConsole);

        $.ajax({
            url: '/oauth-apis/google/gmail/messages/verbose-list/' + oAResultId + '/',
            method: 'POST',
            data: {
                'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                'maxResults': maxResults,
                'pageToken': pageToken,
                'searchQuery': searchQuery
            }
        }).done(function (response) {
            if (response.data) {

                $apiConsole.append('   ' + response.data.length + ' results.\n\n');

                for (i = 0; i < response.data.length; i++) {
                    $apiConsole.append('   email ID: ' + response.data[i].message_id);
                    $apiConsole.append('\n       Sender: ');
                    $(document.createTextNode(response.data[i].sender)).appendTo($apiConsole);
                    $apiConsole.append('\n       Recipients: ');
                    $(document.createTextNode(response.data[i].recipients)).appendTo($apiConsole);
                    $apiConsole.append('\n       Snippet: ');
                    $(document.createTextNode(response.data[i].snippet)).appendTo($apiConsole);
                    $apiConsole.append('\n\n');
                }
                if (response.nextPageToken === '') {
                    $apiConsole.append('\n  No next page token.\n');
                    $nextPageTokenStorage.val('');
                    $nextPageButton.text('First Page');
                } else {
                    $apiConsole.append('\n  Next page token: ' + response.nextPageToken + '\n');
                    $nextPageTokenStorage.val(response.nextPageToken);
                    $nextPageButton.text('Next Page');
                }
                scrollToBottom($apiConsole);
            } else {
                $apiConsole.append('\n\n    There was an error.\n' + response.error + '\n');
                scrollToBottom($apiConsole);
            }
        }).fail(function (response) {
            $apiConsole.append('\n\n    There was an error.\n');
            scrollToBottom($apiConsole);
        });
    }

    function gmailGetEverything(pageToken, maxResults, searchQuery) {
        var oAResultId = $('#oa_result_id').val();
        var $apiConsole = $('#google_api_console_widget');
        var $nextPageTokenStorage = $('#next_page_token');
        var $nextPageButton = $('#gmail_messages_next_page_btn');

        scrollToBottom($apiConsole);

        $.ajax({
            url: '/oauth-apis/google/gmail/messages/get-everything/' + oAResultId + '/',
            method: 'POST',
            data: {
                'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                'maxResults': maxResults,
                'pageToken': pageToken,
                'searchQuery': searchQuery
            }
        }).done(function (response) {
            if (response.data) {

                $apiConsole.append('   ' + response.data.length + ' results.\n\n');

                for (i = 0; i < response.data.length; i++) {
                    $apiConsole.append('   email ID: ' + response.data[i].message_id);
                    $apiConsole.append('\n       Date: ');
                    $(document.createTextNode(response.data[i].date)).appendTo($apiConsole);
                    $apiConsole.append('\n       Sender: ');
                    $(document.createTextNode(response.data[i].sender)).appendTo($apiConsole);
                    $apiConsole.append('\n       Recipients: ');
                    $(document.createTextNode(response.data[i].recipients)).appendTo($apiConsole);
                    $apiConsole.append('\n       Subject: ');
                    $(document.createTextNode(response.data[i].subject)).appendTo($apiConsole);
                    $apiConsole.append('\n       Body: ');
                    // Reference: http://stackoverflow.com/a/17258416
                    $(document.createTextNode(response.data[i].body)).appendTo($apiConsole);
                    $apiConsole.append('\n\n');
                }
                if (response.nextPageToken === '') {
                    $apiConsole.append('\n  No next page token.\n');
                    $nextPageTokenStorage.val('');
                    $nextPageButton.text('First Page');
                } else {
                    $apiConsole.append('\n  Next page token: ' + response.nextPageToken + '\n');
                    $nextPageTokenStorage.val(response.nextPageToken);
                    $nextPageButton.text('Next Page');
                }
                scrollToBottom($apiConsole);
            } else {
                $apiConsole.append('\n\n    There was an error.\n' + response.error + '\n');
                scrollToBottom($apiConsole);
            }
        }).fail(function (response) {
            $apiConsole.append('\n\n    There was an error.\n');
            scrollToBottom($apiConsole);
        });
    }

    function gmailMessagesGet(messageId) {
        var oAResultId = $('#oa_result_id').val();
        var $apiConsole = $('#google_api_console_widget');

        $.ajax({
            url: '/oauth-apis/google/gmail/messages/get/' + oAResultId + '/' + messageId + '/',
            method: 'POST',
            data: {
                'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val()
            }
        }).done(function (response) {
            if (response.data) {
                    $apiConsole.append('   email ID: ' + response.data.message_id);
                    $apiConsole.append('\n       Date: ');
                    $(document.createTextNode(response.data.date)).appendTo($apiConsole);
                    $apiConsole.append('\n       Sender: ');
                    $(document.createTextNode(response.data.sender)).appendTo($apiConsole);
                    $apiConsole.append('\n       Recipients: ');
                    $(document.createTextNode(response.data.recipients)).appendTo($apiConsole);
                    $apiConsole.append('\n       Subject: ');
                    $(document.createTextNode(response.data.subject)).appendTo($apiConsole);
                    $apiConsole.append('\n       Body: ');
                    // Reference: http://stackoverflow.com/a/17258416
                    $(document.createTextNode(response.data.body)).appendTo($apiConsole);
                    $apiConsole.append('\n');
                    scrollToBottom($apiConsole);
            } else {
                $apiConsole.append('\n\n    There was an error.\n' + response.error + '\n');
                scrollToBottom($apiConsole);
            }
        }).fail(function (response) {
            $apiConsole.append('\n\n    There was an error.\n');
            scrollToBottom($apiConsole);
        });
    }

    // "First Page" - "Next Page" button
    $('#gmail_messages_next_page_btn').on('click', function () {
        var oAResultId = $('#oa_result_id').val();
        var maxResults = $('#gmail_messages_list_max_results').val().trim();
        var searchQuery = $('#api_console_search_query').val();
        var nextPageToken = $('#next_page_token').val();
        var $apiConsole = $('#google_api_console_widget');
        var $selectedDetailLevelButton = $('.selected-detail-level');
        var $nextPageButton = $('#gmail_messages_next_page_btn');

        if (nextPageToken === '') {
            $apiConsole.append('\n  ##### Listing first page, capped to ' + maxResults + ' emails...');
        } else {
            $apiConsole.append('\n  ##### Listing next page (ID ' + nextPageToken + '), capped to ' + maxResults + ' emails...');
        }
        scrollToBottom($apiConsole);

        if ($selectedDetailLevelButton.attr('id') === 'gmail_messages_list_btn') {
            gmailMessagesList(nextPageToken, maxResults, searchQuery);
        } else if ($selectedDetailLevelButton.attr('id') === 'gmail_messages_verbose_list_btn') {
            gmailDetailedList(nextPageToken, maxResults, searchQuery);
        } else if ($selectedDetailLevelButton.attr('id') === 'gmail_messages_get_everything_btn') {
            gmailGetEverything(nextPageToken, maxResults, searchQuery);
        } else {
            $apiConsole.append('\n\n   Select a detail level first.\n\n');
            scrollToBottom($apiConsole);
        }
    });

    // "Get page by token" button
    $('#gmail_messages_get_page_btn').on('click', function () {
        var oAResultId = $('#oa_result_id').val();
        var maxResults = $('#gmail_messages_list_max_results').val().trim();
        var searchQuery = $('#api_console_search_query').val();
        var messagePageId = $('#gmail_messages_page_token').val().trim();
        var $apiConsole = $('#google_api_console_widget');
        var $selectedDetailLevelButton = $('.selected-detail-level');
        var $nextPageButton = $('#gmail_messages_next_page_btn');

        if (messagePageId === '') {
            $apiConsole.append('\n  Enter a page token to list results.\n');
            scrollToBottom($apiConsole);
        } else {
            $apiConsole.append('\n  ##### Getting page with ID ' + messagePageId + ', capped to ' + maxResults + ' emails...');
            scrollToBottom($apiConsole);

            if ($selectedDetailLevelButton.attr('id') === 'gmail_messages_list_btn') {
                gmailMessagesList(messagePageId, maxResults, searchQuery);
            } else if ($selectedDetailLevelButton.attr('id') === 'gmail_messages_verbose_list_btn') {
                gmailDetailedList(messagePageId, maxResults, searchQuery);
            } else if ($selectedDetailLevelButton.attr('id') === 'gmail_messages_get_everything_btn') {
                gmailGetEverything(messagePageId, maxResults, searchQuery);
            } else {
                $apiConsole.append('\n\n   Select a detail level first.\n\n');
                scrollToBottom($apiConsole);
            }
        }
    });

    // "Get email body by ID" button
    $('#gmail_messages_get_btn').on('click', function () {
        var oAResultId = $('#oa_result_id').val();
        var messageId = $('#gmail_messages_get_id').val().trim();
        var $apiConsole = $('#google_api_console_widget');

        if (messageId === '') {
            $apiConsole.append('\n  Enter an email ID to get its contents.\n');
            scrollToBottom($apiConsole);
        } else {
            $apiConsole.append('\n  ##### Getting details for email ' + messageId);
            scrollToBottom($apiConsole);
            gmailMessagesGet(messageId);
        }
    });

    // Gdrive API console

    function gdriveFilesList(directoryId, pageSize, includeDirectories, includeFiles, includeDetails, searchQuery) {
        var oAResultId = $('#oa_result_id').val();
        var $apiConsole = $('#google_api_console_widget');

        if (pageSize === '') {
            pageSize = '10';
        }
        if ($('.list-selection-type-btn.selected-content-type').length === 0) {
            $apiConsole.append('\n\n   Directories and files cannot both be unchecked.\n\n');
            scrollToBottom($apiConsole);
            return;
        }

        $apiConsole.append('\n  ##### Listing');
        if (includeDirectories === false) {
            $apiConsole.append(' files');
        } else if (includeFiles === false) {
            $apiConsole.append(' directories');
        } else {
            $apiConsole.append(' directories and files')
        }
        if (directoryId != '') {
             $apiConsole.append(' in directory with ID ' + directoryId);
        }
        $apiConsole.append(', capped to ' + pageSize + ' results');
        if (searchQuery != '') {
            $apiConsole.append(', using search query "' + searchQuery + '"');
        }
        $apiConsole.append(' ...');
        scrollToBottom($apiConsole);

        $.ajax({
            url: '/oauth-apis/google/drive/files/list/' + oAResultId + '/',
            method: 'POST',
            data: {
                'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                'pageSize': pageSize,
                'directoryId': directoryId,
                'searchQuery': searchQuery,
                'includeDirectories': includeDirectories,
                'includeFiles': includeFiles,
                'includeDetails': includeDetails
            }
        }).done(function (response) {
            if (response.data) {

                $apiConsole.append('   ' + response.data.files.length + ' results.\n\n');

                for (i = 0; i < response.data.files.length; i++) {
                    var fileOrDirectory = 'file';
                    if (response.data.files[i].mimeType === 'application/vnd.google-apps.folder') {
                        fileOrDirectory = 'directory';
                    }
                    $apiConsole.append('   ' + fileOrDirectory + ' ID: ' + response.data.files[i].id);

                    if (includeDetails) {
                        if (response.data.files[i].parents) {
                            $apiConsole.append('\n       parent directories: ');
                            $(document.createTextNode(response.data.files[i].parents)).appendTo($apiConsole);
                        }
                        if (response.data.files[i].name) {
                            $apiConsole.append('\n       name: ');
                            $(document.createTextNode(response.data.files[i].name)).appendTo($apiConsole);
                        }
                        if (response.data.files[i].size) {
                            $apiConsole.append('\n       size: ');
                            $(document.createTextNode(response.data.files[i].size)).appendTo($apiConsole);
                        }
                        if (response.data.files[i].mimeType) {
                            $apiConsole.append('\n       mimeType: ');
                            $(document.createTextNode(response.data.files[i].mimeType)).appendTo($apiConsole);
                        }
                        if (response.data.files[i].createdTime) {
                            $apiConsole.append('\n       createdTime: ');
                            $(document.createTextNode(response.data.files[i].createdTime)).appendTo($apiConsole);
                        }
                        if (response.data.files[i].modifiedTime) {
                            $apiConsole.append('\n       modifiedTime: ');
                            $(document.createTextNode(response.data.files[i].modifiedTime)).appendTo($apiConsole);
                        }
                        $apiConsole.append('\n');
                    }
                    $apiConsole.append('\n');
                }
                scrollToBottom($apiConsole);
            } else if (response.error) {
                $apiConsole.append('\n\n    There was an error.\n' + response.error + '\n');
                scrollToBottom($apiConsole);
            } else if (response.gdrive_error) {
                $apiConsole.append('\n\n    Google Drive returned an error.\n' + response.gdrive_error + '\n');
                scrollToBottom($apiConsole);
            }
        }).fail(function (response) {
            $apiConsole.append('\n\n    There was an error.\n');
            scrollToBottom($apiConsole);
        });
    }

    // Tells the server to download a file to its file system.
    function gdriveFileDownload(fileId) {
        var oAResultId = $('#oa_result_id').val();
        var $apiConsole = $('#google_api_console_widget');

        scrollToBottom($apiConsole);

        $.ajax({
            url: '/oauth-apis/google/drive/files/download/' + oAResultId + '/',
            method: 'POST',
            data: {
                'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                'fileIds': [fileId],
            }
        }).done(function (response) {
            if (response.data) {
                $apiConsole.append(' Success.');
                $apiConsole.append('\n\n   File saved at: ' + response.data[0].path + '\n\n      (Reload the page to see it in the plunder list as ID ' + response.data[0].plunder_id + ')\n\n');
            } else if (response.error) {
                $apiConsole.append('\n\n    There was an error.\n' + response.error + '\n');
            } else if (response.gdrive_error) {
                $apiConsole.append('\n\n    Google Drive returned an error.\n' + response.gdrive_error + '\n');
            } else {
                $apiConsole.append('\n\n    There was an error.\n');
            }
                scrollToBottom($apiConsole);
        }).fail(function (response) {
            $apiConsole.append('\n\n    There was an error.\n');
            scrollToBottom($apiConsole);
        });
    }

    // Swaps maximized and minimized states of gdrive panel components
    $('#google_api_console_panel_swapper').on('click', function () {
        var $minMaxButton = $(this);
        var $jsTreeContainer = $('#gdrive_jstree_container');
        var $consoleContainer = $('#google_api_console_widget');

        if ($minMaxButton.hasClass("api-console-panel-swapper-minimized")) {
            $jsTreeContainer.removeClass("api-jstree-widget-maximized").addClass("api-jstree-widget-minimized");
            $consoleContainer.removeClass("api-console-widget-minimized").addClass("api-console-widget-maximized");
            $minMaxButton.removeClass("api-console-panel-swapper-minimized").addClass("api-console-panel-swapper-maximized");
            $minMaxButton.text("Minimize");
        } else {
            $jsTreeContainer.removeClass("api-jstree-widget-minimized").addClass("api-jstree-widget-maximized");
            $consoleContainer.removeClass("api-console-widget-maximized").addClass("api-console-widget-minimized");
            $minMaxButton.removeClass("api-console-panel-swapper-maximized").addClass("api-console-panel-swapper-minimized");
            $minMaxButton.text("Maximize");
            scrollToBottom($('#google_api_console_widget'));
        }
    });

    // "Root Directory" button
    $('#root_directory_btn').on('click', function () {
        var directoryId = 'root';
        var pageSize = $('#drive_files_list_page_size').val().trim();
        var includeDirectories = $('#drive_list_directories_btn').hasClass('selected-content-type');
        var includeFiles = $('#drive_list_files_btn').hasClass('selected-content-type');
        var includeDetails = $('#drive_list_detail_btn').hasClass('selected-content-type');
        var searchQuery = $('#api_console_search_query').val();
        gdriveFilesList(directoryId, pageSize, includeDirectories, includeFiles, includeDetails, searchQuery);
    });

    // "Get directory by ID" button
    $('#drive_files_get_directory_btn').on('click', function () {
        var directoryId = $('#drive_files_directory_input').val().trim();
        var pageSize = $('#drive_files_list_page_size').val().trim();
        var includeDirectories = $('#drive_list_directories_btn').hasClass('selected-content-type');
        var includeFiles = $('#drive_list_files_btn').hasClass('selected-content-type');
        var includeDetails = $('#drive_list_detail_btn').hasClass('selected-content-type');
        var searchQuery = $('#api_console_search_query').val();
        gdriveFilesList(directoryId, pageSize, includeDirectories, includeFiles, includeDetails, searchQuery);
    });

    // "Search" button click search submission
    $('#drive_files_search_btn').on('click', function () {
        var directoryId = '';
        var pageSize = $('#drive_files_list_page_size').val().trim();
        var includeDirectories = $('#drive_list_directories_btn').hasClass('selected-content-type');
        var includeFiles = $('#drive_list_files_btn').hasClass('selected-content-type');
        var includeDetails = $('#drive_list_detail_btn').hasClass('selected-content-type');
        var searchQuery = $('#api_console_search_query').val();
        gdriveFilesList(directoryId, pageSize, includeDirectories, includeFiles, includeDetails, searchQuery);
    });

    // "Search" input field enter keypress search submission
    $('#api_console_search_query').keydown(function(event) {
        if (event.keyCode == 13) {
            // Reference: http://stackoverflow.com/a/11001925
            event.preventDefault();
            var directoryId = '';
            var pageSize = $('#drive_files_list_page_size').val().trim();
            var includeDirectories = $('#drive_list_directories_btn').hasClass('selected-content-type');
            var includeFiles = $('#drive_list_files_btn').hasClass('selected-content-type');
            var includeDetails = $('#drive_list_detail_btn').hasClass('selected-content-type');
            var searchQuery = $('#api_console_search_query').val();
            gdriveFilesList(directoryId, pageSize, includeDirectories, includeFiles, includeDetails, searchQuery);
        }
    });

    // "Download file by ID" button
    $('#drive_files_download_btn').on('click', function () {
        var fileId = $('#drive_files_download_id').val().trim();
        gdriveFileDownload(fileId);
    });

    // jsTree for gdrive

    function gdriveJsTreeUpdate(directoryId, callback) {
        var oAResultId = $('#oa_result_id').val();
        var pageSize = 100;
        var includeDirectories = true;
        var includeFiles = true;
        var includeDetails = true;
        var searchQuery = '';
        var $apiConsole = $('#google_api_console_widget');

        $.ajax({
            url: '/oauth-apis/google/drive/files/list/' + oAResultId + '/',
            method: 'POST',
            data: {
                'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                'pageSize': 100,
                'directoryId': directoryId,
                'searchQuery': '',
                'includeDirectories': true,
                'includeFiles': true,
                'includeDetails': true,
                'jsTreeUpdate': true
            }
        }).done(function (response) {
            if (response.data) {
                var newDirectoryContents = [];
                var hasChildren = false;

                $.each(response.data.files, function(index, file) {
                    if (file.mimeType === "application/vnd.google-apps.folder") {
                        hasChildren = true;
                        nodeType = "default";
                    } else {
                        hasChildren = false;
                        nodeType = "file";
                    }
                    newDirectoryContents.push({
                        "id": file.id,
                        "text": file.name,
                        "children": hasChildren,
                        "type": nodeType
                    });
                });

                callback(newDirectoryContents);

            } else if (response.error) {
                $apiConsole.append('\n    There was an error while getting list data for jsTree:\n' + response.error);
            } else if (response.gdrive_error) {
                $apiConsole.append('\n    Google Drive returned an error while getting list data for jsTree.\n' + response.gdrive_error);
            }
        }).fail(function (response) {
            $apiConsole.append('\n    There was an error while attempting to get list data for jsTree.\n');
        });
    }

    function gdriveFilesBatchDownload(fileIds) {
        var oAResultId = $('#oa_result_id').val();
        var $apiConsole = $('#google_api_console_widget');

        $apiConsole.append('\n  ##### Downloading files with IDs ' + fileIds + ' ...');
        scrollToBottom($apiConsole);

        $.ajax({
            url: '/oauth-apis/google/drive/files/download/' + oAResultId + '/',
            method: 'POST',
            data: {
                'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                'fileIds': fileIds,
            }
        }).done(function (response) {
            if (response.data) {

                $apiConsole.append(' Success.');

                $.each(response.data, function (index, element) {
                    if (response.data[index].error) {
                        $apiConsole.append('\n    Error downloading ' + response.data[index].fileId + ': ' + response.data[index].error + '\n')
                    } else {
                        $apiConsole.append('\n    File with ID ' + response.data[index].fileId + ' saved. (Reload the page to see it in the plunder list as ID ' + response.data[index].plunder_id + ')');
                    }
                    scrollToBottom($apiConsole);
                });
            } else if (response.error) {
                $apiConsole.append('\n    There was an error:\n' + response.error + '\n');
            } else if (response.gdrive_error) {
                $apiConsole.append('\n    Google Drive returned an error.\n' + response.gdrive_error + '\n');
            } else {
                $apiConsole.append('\n    There was an error.\n');
            }
            scrollToBottom($apiConsole);
        }).fail(function (response) {
            $apiConsole.append('\n    There was an error.\n');
            scrollToBottom($apiConsole);
        });
    }

    // jsTree init and settings
    $(function () {
        if ($('#gdrive_jstree').length != 0) {
            $('#gdrive_jstree').jstree({
                "core": {
                    "animation": 0,
                    "check_callback": true,
                    "themes": {
                        "stripes": true
                    },
                    // The return value of callback will be used as the node.
                    "data": function (node, callback) {
                        if (node.id === "#") {
                            callback([{"text" : "Root", "id" : "root", "children" : true}]);
                        } else {
                            gdriveJsTreeUpdate(node.id, callback);
                        }
                    }
                },
                "types": {
                    "#": {
                        "max_children": 1,
                        "max_depth": 4,
                        "valid_children": ["root"]
                    },
                    "root": {
                        "icon": "glyphicon glyphicon-hdd",
                        "valid_children": ["default"]
                    },
                    "default": {
                        "icon": "glyphicon glyphicon-folder-open",
                        "valid_children": ["default", "file"]
                    },
                    "file": {
                        "icon": "glyphicon glyphicon-file",
                        "valid_children": []
                    }
                },
                "checkbox" : {
                  "keep_selected_style" : false
                },
                "plugins": ["contextmenu", "dnd", "search",
                            "state", "types", "wholerow", "checkbox"]
            });
        }
    });

    // jsTree file browser panel "Download checked files" button
    $('#gdrive_jstree_info_panel_download_checked').on('click', function () {
        var checkedNodes = $("#gdrive_jstree").jstree('get_checked');
        gdriveFilesBatchDownload(checkedNodes);
    });

    // Google API common

    // Switches toggled state for all Google API console list detail toggles
    $('.list-detail-toggle').on('click', function () {
        $('.list-detail-toggle').removeClass('btn-dark-green selected-detail-level');
        $(this).addClass('btn-dark-green selected-detail-level');
    });

    // Swaps toggled state for gdrive console content type toggles
    $('.list-content-toggle').on('click', function () {
        var $contentToggleBtn = $(this);
        if ($contentToggleBtn.hasClass('selected-content-type')) {
            $contentToggleBtn.removeClass('btn-dark-green selected-content-type');
        } else {
            $contentToggleBtn.addClass('btn-dark-green selected-content-type');
        }
    });

    $('#api_console_clear_btn').on('click', function () {
        $('#google_api_console_widget').text('');
    });

    $('#api_console_reset_btn').on('click', function () {
        $('#google_api_console_widget').text('');
        $('#api_console_search_query').val('');
        resetGmailListPage();
    });

    $('#api_console_download_console_btn').on('click', function () {
        downloadAsTextFile($('#google_api_console_widget').val());
    });

    // ShoalScrape

    // Updates ShoalScrapeTask state for the editShoalScrapeTask main toggle button only.
    (function editShoalScrapeTaskCheckState() {
        var isActive = true;
        var url = '/shoalscrape-tasks/check-status/';
        var delay = 1000;
        var $btn = $('#shoalscrape_task_edit .shoalscrape-task-control');
        var $span = $('#shoalscrape_task_edit .shoalscrape-tasks-edit-status-text');
        var ids = [$('#id_shoalscrape_task_id').val()];

        if ($btn.length) {
            (function checkItems() {
                $.ajax({
                    url: url,
                    method: 'POST',
                    data: {
                        'ids': ids
                    }
                }).done(function (response) {
                    if (!response.error) {
                        var shoalScrapeTaskControlClasses = 'glyphicon-minus glyphicon-refresh glyphicon-pause glyphicon-remove glyphicon-ok btn-light-blue btn-light-green btn-grey btn-red btn-dark-green';
                        if (response[0].status[0] === 0) {
                            $btn.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-minus btn-light-blue');
                            $span.text('Not started').qtip('destroy', true).attr('title', 'Not started').removeClass('shoalscrape-task-error-tag');
                        } else if (response[0].status[0] === 1) {
                            $btn.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-refresh btn-light-green');
                            $span.text('In progress').qtip('destroy', true).attr('title', 'In progress').removeClass('shoalscrape-task-error-tag');
                        } else if (response[0].status[0] === 2) {
                            $btn.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-pause btn-grey');
                            $span.text('Paused').qtip('destroy', true).attr('title', 'Paused').removeClass('shoalscrape-task-error-tag');
                        } else if (response[0].status[0] === 3) {
                            $btn.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-remove btn-red');
                            $span.text('Error').attr('title', response[0].status[1]).addClass('shoalscrape-task-error-tag');
                            if ($span[0].hasAttribute('data-hasqtip')) {
                                $span.qtip('enable');
                            } else {
                                applyQtip($span);
                            }
                        } else if (response[0].status[0] === 4) {
                            $btn.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-ok btn-dark-green');
                            $span.text('Completed').qtip('destroy', true).attr('title', 'Completed').removeClass('shoalscrape-task-error-tag');
                        }
                    }
                    if (isActive) {
                        setTimeout(checkItems, delay);
                    }
                });
            })();
        }
    })();

    // Updates ShoalScrapeTask state for all the listShoalScrapeTask toggle buttons.
    (function listShoalScrapeTaskCheckState() {
        var delay = 2000;
        var isActive = true;

        var $table = $('#shoalscrape_tasks_list').parents('table');
        if ($table.length) {

            var url = '/shoalscrape-tasks/check-status/';
            var ids = $.map($table.find('tr[data-id]'), function (e) {
                return $(e).data('id');
            });

            (function checkItems() {
                $.ajax({
                    url: url,
                    method: 'POST',
                    data: {
                        'ids': ids
                    }
                }).done(function (response) {
                    if (!response.error) {
                        var shoalScrapeTaskControlClasses = 'glyphicon-minus glyphicon-refresh glyphicon-pause glyphicon-remove glyphicon-ok btn-light-blue btn-light-green btn-grey btn-red btn-dark-green';
                        response.forEach(function (k) {
                            var $row = $table.find('tr[data-id="' + k['id'] + '"]');
                            var $btn = $row.first('td').find('.shoalscrape-task-control');
                            var $span = $row.find('span.shoalscrape-tasks-list-status-text');
                            if (k['status'][0] === 0) {
                                $btn.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-minus btn-light-blue');
                                $span.text('Not started').qtip('destroy', true).attr('title', 'Not started').removeClass('shoalscrape-task-error-tag');
                            } else if (k['status'][0] === 1) {
                                $btn.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-refresh btn-light-green');
                                $span.text('In progress').qtip('destroy', true).attr('title', 'In progress').removeClass('shoalscrape-task-error-tag');
                            } else if (k['status'][0] === 2) {
                                $btn.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-pause btn-grey');
                                $span.text('Paused').qtip('destroy', true).attr('title', 'Paused').removeClass('shoalscrape-task-error-tag');
                            } else if (k['status'][0] === 3) {
                                $btn.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-remove btn-red');
                                $span.text('Error').attr('title', k['status'][1]).addClass('shoalscrape-task-error-tag');
                                if ($span[0].hasAttribute('data-hasqtip')) {
                                    $span.qtip('enable');
                                } else {
                                    applyQtip($span);
                                }
                            } else if (k['status'][0] === 4) {
                                $btn.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-ok btn-dark-green');
                                $span.text('Completed').qtip('destroy', true).attr('title', 'Completed').removeClass('shoalscrape-task-error-tag');
                            }
                        });
                    }
                    if (isActive) {
                        setTimeout(checkItems, delay);
                    }
                });
            })();
        }
    })();

    // Handles the behavior of ShoalScrape toggle buttons
    $('.shoalscrape-task-control').on('click', function() {
        var $startTaskButton = $(this);
        var shoalScrapeTaskId = $startTaskButton.attr('data-shoalscrape-task');

        // Reference for the bit on the end: http://stackoverflow.com/a/15651670
        var $shoalScrapeTaskControlButton = $('.shoalscrape-task-control').filter(function() { return $(this).data('shoalscrape-task') == shoalScrapeTaskId; });
        var $span = $shoalScrapeTaskControlButton.parents('tr').find('span.shoalscrape-tasks-list-status-text');
        var shoalScrapeTaskControlClasses = 'glyphicon-minus glyphicon-refresh glyphicon-pause glyphicon-remove glyphicon-ok btn-light-blue btn-light-green btn-grey btn-red btn-dark-green';

        if ($startTaskButton.is('.glyphicon-refresh')) {
            confirm1 = confirm("This ShoalScrape task ( id: " + shoalScrapeTaskId + " ) is currently in progress. Are you sure that you want to pause it?\n\nThis will reset the task's progress.");
        } else {
            confirm1 = confirm("This ShoalScrape task ( id: " + shoalScrapeTaskId + " ) is currently paused. Are you sure that you want to start it?");
        }

        if (confirm1) {
            // Tell the server to toggle the ShoalScrapeTask.
            $.ajax({
                url: '/shoalscrape-tasks/start-stop-shoalscrape-task/',
                method: 'POST',
                data: {'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                       'shoalscrape_task_id': shoalScrapeTaskId}
            }).done(function(response) {
                // Swap icons and text as required by the new ShoalScrapeTask state.
                if (response.state === 0) {
                    $shoalScrapeTaskControlButton.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-minus btn-light-blue');
                    $span.text('Not started').removeClass('shoalscrape-task-error-tag');
                } else if (response.state === 1) {
                    $shoalScrapeTaskControlButton.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-refresh btn-light-green');
                    $span.text('In progress').removeClass('shoalscrape-task-error-tag');
                } else if (response.state === 2) {
                    $shoalScrapeTaskControlButton.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-pause btn-grey');
                    $span.text('Paused').removeClass('shoalscrape-task-error-tag');
                } else if (response.state === 3) {
                    $shoalScrapeTaskControlButton.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-remove btn-red');
                    $span.text('Error').addClass('shoalscrape-task-error-tag');
                } else if (response.state === 4) {
                    $shoalScrapeTaskControlButton.removeClass(shoalScrapeTaskControlClasses).addClass('glyphicon-ok btn-dark-green');
                    $span.text('Completed').removeClass('shoalscrape-task-error-tag');
                }
            });
        }
    });

    // Updates the ShoalScrapeTask log file display on the editShoalScrapeTask page.
    (function shoalScrapeTaskGetLog() {
        var delay = 5000;
        var isActive = true;
        var $logDisplay = $('#shoalscrape_console_widget');

        if ($logDisplay.length) {
            var $autoUpdateToggle = $('#auto_update_toggle');
            var $startTaskButton = $('.shoalscrape-task-control');
            var shoalScrapeTaskId = $startTaskButton.attr('data-shoalscrape-task');

            (function updateLogDisplay() {
                $.ajax({
                    url: '/shoalscrape-tasks/get-log/' + shoalScrapeTaskId + '/',
                    method: 'GET'
                }).done(function (response) {

                    if ($autoUpdateToggle.hasClass('btn-dark-green')) {
                        $logDisplay.text('');

                        if (response.log_file_contents) {
                            for (i = 0; i < response.log_file_contents.length; i++) {
                                $(document.createTextNode(response.log_file_contents[i])).appendTo($logDisplay);
                            }
                        }
                        scrollToBottom($logDisplay);
                    }
                    if (isActive) {
                        setTimeout(updateLogDisplay, delay);
                    }

                });
            })();
        }
    })();

    // Swaps the auto-update toggle
    $('#auto_update_toggle').on('click', function () {
        $btn = $(this);
        if ($btn.hasClass('btn-dark-green')) {
            $btn.removeClass('btn-dark-green');
            $btn.text('Auto-update off');
        } else {
            $btn.addClass('btn-dark-green');
            $btn.text('Auto-update on');
        }
    });

    // Data management checkbox list toggles
    $('.toggle-all-checkboxes').on('click', function () {
        var $toggleAllButton = $(this);
        if ($toggleAllButton.attr('id') === 'toggle_scraper_user_agents') {
            var $checkboxes = $('#data_export_form #id_scraper_user_agents :checkbox');
            var text = 'Scraper User Agents';
        } else if ($toggleAllButton.attr('id') === 'toggle_landing_pages') {
            var $checkboxes = $('#data_export_form #id_landing_pages :checkbox');
            var text = 'Landing Pages';
        } else if ($toggleAllButton.attr('id') === 'toggle_redirect_pages') {
            var $checkboxes = $('#data_export_form #id_redirect_pages :checkbox');
            var text = 'Redirect Pages';
        } else if ($toggleAllButton.attr('id') === 'toggle_email_templates') {
            var $checkboxes = $('#data_export_form #id_email_templates :checkbox');
            var text = 'Email Templates';
        }
        if ($toggleAllButton.hasClass('btn-dark-green')) {
            $toggleAllButton.removeClass('btn-dark-green').text('Check all ' + text);
            $checkboxes.prop('checked', false);
        } else {
            $toggleAllButton.addClass('btn-dark-green').text('Uncheck all ' + text);
            $checkboxes.prop('checked', true);
        }
    });

    // Refreshes the Data Management page when a file is successfully uploaded
    // Reference: http://stackoverflow.com/a/22070289
    if (typeof window["Dropzone"] !== "undefined") {
        Dropzone.autoDiscover = false;

        $(document).ready(function() {
            var dropzoneForm = new Dropzone("#data_import_form", {
                url: "/import-data/",
                maxFilesize: "100",  // MiB?
            });

            dropzoneForm.on("complete", function (file) {
                if (this.getUploadingFiles().length === 0 && this.getQueuedFiles().length === 0) {
                    location.reload();
                }
            });
        });
    }
});

function parseTimeString(timeString) {
    var date = {
        hours: 0,
        minutes: 0,
        seconds: 0
    };
    if (timeString.length) {
        var parsedTime = timeString.match(/(\d\d):(\d\d):(\d\d)/);
        date.hours = parseInt(parsedTime[1]);
        date.minutes = parseInt(parsedTime[2]);
        date.seconds = parseInt(parsedTime[3]);
        return date;
    } else {
        return date;
    }
}

function minutesToTimeString(minutes) {
    var decimal_time = minutes / 60;
    var hours = Math.floor(decimal_time);
    var minutes = Math.round(((decimal_time) % 1) * 60);
    var timeString = zfill(hours, 2) + ":" + zfill(minutes, 2) + ":00"
    return timeString;
}

// reference: https://github.com/andrewrk/node-zfill/blob/master/index.js
function zfill(number, size) {
    number = number.toString();
    while (number.length < size) {
        number = "0" + number;
    }
    return number;
};

function applyQtip(element) {
    element.qtip({
        show: 'click',
        hide: 'unfocus',
        style: {
            tip: {
                corner: 'left center'
            },
            classes: 'qtip-tipped qtip-light qtip-shadow engagement-error-tooltip shoalscrape-task-error-tooltip'
        },
        position: {
            my: 'left-center',
            at: 'right-center'
        },
        // Reference: http://craigsworks.com/projects/forums/showthread.php?tid=2143
        events: {
            render: function(event, api) {
                $(window).bind('keydown', function(e) {
                    if (e.keyCode === 27) {
                        api.hide(e);
                    }
                });
            }
        }
    });
};

$(function() {
    applyQtip($('.engagement-error-tag, .vector-email-error-tag, .shoalscrape-task-error-tag'));
});

function loadTargetList(campaign_id) {
    var checkedTl = $('input[name="target_lists"]:checked').map(function(){
        return parseInt(this.value);
    });
    var disabledTl = $('input[name="target_lists"]:disabled').map(function(){
        return parseInt(this.value);
    });
    $.ajax({
        url: '/engagements/get-target-list/' + campaign_id + '/',
        method: 'GET'
    }).done(function (response) {
        if (response.success) {
            $('#id_target_lists').empty()
            $.each(response.targetList, function(k, v) {
                $('#id_target_lists').append(
                    $('<div/>', {'class': 'checkbox'}).append(
                        $('<label/>', {'for': 'id_target_lists_'+k, 'text': ' '+v.name}).prepend(
                            $('<input/>', {'name': 'target_lists',
                                        'id': 'id_target_lists_'+k,
                                        'value': v.id,
                                        'type': 'checkbox',
                                        'checked': $.inArray(v.id, checkedTl) != -1 ? 'checked' : false,
                                        'disabled': $.inArray(v.id, disabledTl) != -1 ? 'disabled' : false})
                        )
                    )
                );
            });
            if($('#id_target_lists').height() > 420) {
                $('#id_target_lists').height(420);
            } else {
                $('#id_target_lists').height('auto');
            }
        }
    });
}

// Saving steps for add/edit entities
function saveStep(entity, id) {
    var steps = JSON.parse(localStorage.getItem('steps'));
    if(steps == null || steps == "[]") {
        steps = [];
    }

    if(entity == 'campaign') {
        steps.push({
            entity: entity,
            id: id,
            client: $('select[name="client"]').val(),
            name: $('input[name="name"]').val(),
            description: $('textarea[name="description"]').val(),
            redirected: false
        });
    } else if(entity == 'client') {
        steps.push({
            entity: entity,
            id: id,
            name: $('input[name="name"]').val(),
            url: $('input[name="url"]').val(),
            default_time_zone: $('select[name="default_time_zone"]').val(),
            redirected: false
        })
    } else if(entity == 'engagement') {
        var cbs = $('input[type="checkbox"]');
        var cbs_checked = [];
        cbs.each(function() {
            if($(this).prop('checked')) {
                cbs_checked.push({
                    id: $(this).attr('id'),
                    checked: true
                })
            }
        });
        var loc = window.location.href.split('/');
        if(loc[loc.length - 1] != "") {
            id = loc[loc.length - 1];
        } else if (loc[loc.length - 2] != "") {
            id = loc[loc.length - 2];
        }
        steps.push({
            entity: entity,
            id: id,
            campaign: $('select[name="campaign"]').val(),
            name: $('input[name="name"]').val(),
            description: $('textarea[name="description"]').val(),
            schedule: $('select[name="schedule"]').val(),
            email_template: $('select[name="email_template"]').val(),
            landing_page: $('select[name="landing_page"]').val(),
            cbs: cbs_checked,
            redirected: false
        })
    }

    localStorage.setItem('steps', JSON.stringify(steps));
}

function removeEntity(entity, id) {
    var confirm1 = confirm("Are you sure that you want to remove this record?");
    if(confirm1) {
        $.ajax({
            method: 'POST',
            url: '/' + entity + '/delete/' + id + '/',
            success: function(data) {
                if (data.success) {
                    window.location.href = "/" + entity + "/list/";
                } else {
                    alert(data.message);
                }
            }
        })
    }
}

function removeEntityWithoutRedirect(entity, id) {
    var confirm1 = confirm("Are you sure that you want to remove this record?");
    if(confirm1) {
        $.ajax({
            method: 'POST',
            url: '/' + entity + '/delete/' + id + '/',
            success: function(data) {
                if (data.success) {
                    window.location.reload();
                } else {
                    alert(data.message);
                }
            },
        })
    }
}
