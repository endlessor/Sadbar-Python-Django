CKEDITOR.editorConfig = function( config ) {
  config.skin = 'bootstrapck';
  config.toolbar = [
    {'name': 'tools', 'items': ['ShowBlocks', 'Preview', 'Maximize',
      '-', 'Source']},
    {'name': 'styles', 'items': ['Styles', 'Format', 'Font', 'FontSize']},
    {'name': 'links', 'items': ['Link', 'Unlink', 'Anchor']},
    {'name': 'basicstyles',
      'items': ['Bold', 'Italic', 'Underline', 'Strike', 'Subscript',
        'Superscript', '-', 'RemoveFormat']},
    '/',
    {'name': 'insert',
      'items': ['Image', 'Flash', 'Table', 'HorizontalRule', 'Smiley',
        'SpecialChar', 'PageBreak', 'Iframe']},
    {'name': 'paragraph',
      'items': ['NumberedList', 'BulletedList', '-', 'Outdent',
        'Indent', '-', 'Blockquote', 'CreateDiv', '-',
        'JustifyLeft', 'JustifyCenter', 'JustifyRight',
        'JustifyBlock', '-', 'BidiLtr', 'BidiRtl', 'Language']},
    {'name': 'colors', 'items': ['TextColor', 'BGColor']}
  ];
  config.tabSpaces = 4;
  config.extraPlugins = [
    'div',
    'autolink',
    'autoembed',
    'embedsemantic',
    'autogrow',
    'widget',
    'lineutils',
    'dialog',
    'dialogui',
    'elementspath'
  ].join(',');
  config.height = 300;
  config.width = 800;
  config.fullPage = true;
  config.allowedContent = true;
  config.filebrowserBrowseUrl = '/ckeditor/browse/';
  config.filebrowserUploadUrl = '/ckeditor/upload/';
};
