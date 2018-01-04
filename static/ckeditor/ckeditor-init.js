(function() {
  var djangoJQuery;
  if (typeof jQuery == 'undefined' && typeof django == 'undefined') {
    console.error('ERROR django-ckeditor missing jQuery. Set CKEDITOR_JQUERY_URL or provide jQuery in the template.');
  } else if (typeof django != 'undefined') {
    djangoJQuery = django.jQuery;
  }

  var $ = jQuery || djangoJQuery;
  $(function() {
    initialiseCKEditor();
    initialiseCKEditorInInlinedForms();

    function initialiseCKEditorInInlinedForms() {
      try {
        $(document).on("click", ".add-row a, .grp-add-handler", function () {
          initialiseCKEditor();
          return true;
        });
      } catch (e) {
        $(document).delegate(".add-row a, .grp-add-handler", "click",  function () {
          initialiseCKEditor();
          return true;
        });
      }
    }

    function initialiseCKEditor() {
      $('textarea[data-type=ckeditortype]').each(function(){
        if($(this).data('processed') == "0" && $(this).attr('id').indexOf('__prefix__') == -1){
          $(this).data('processed',"1");
          $($(this).data('external-plugin-resources')).each(function(){
              CKEDITOR.plugins.addExternal(this[0], this[1], this[2]);
          });
          CKEDITOR.replace($(this).attr('id'), $(this).data('config'));
        }
      });

        var help_select = $('#helper_select');
        var help_label = help_select.parent().next();
        help_select.change(function () {
            var val = help_select.val();
            if (val) {
                $.ajax({
                    url: '/email-templates/get-variables/',
                    method: 'POST',
                    data: {
                        'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                        'list_id': val
                    }
                }).done(function (res) {
                    if (res.success) {
                        help_label.html('You can use [#[url]#], [#[firstname]#], [#[lastname]#], [#[email]#], [#[timezone]#]' + (res.data ? ', ' : '') + res.data + ' variables')
                    }
                });
            }
        });

        var $check_shortcodes = $('#check_shortcodes');
        $check_shortcodes.on('click', function () {
            var list_id = help_select.val();
            var $shortcode_errors = $('#shortcode_errors');
            if (!list_id) {
                $shortcode_errors.html('<span>Select a target list to verify valid shortcode usage.</span>')
            } else if (typeof CKEDITOR != 'undefined') {
                $.ajax({
                    url: '/email-templates/check-shortcodes/',
                    method: 'POST',
                    data: {
                        'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                        'list_id': list_id,
                        'template': CKEDITOR.instances.id_template.getData()
                    }
                }).done(function (response) {
                    if (response.shortcode_errors.length > 0) {
                        $shortcode_errors.html('<span style="color: red;">' + response.shortcode_errors + '</span>');
                    }
                    else {
                        $shortcode_errors.html('<span style="color: green;">No invalid shortcodes found.</span>');
                    }
                });
            }
        });

    }
  });
}());
