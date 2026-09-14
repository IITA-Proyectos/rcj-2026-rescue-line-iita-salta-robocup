app.config(['$translateProvider', function ($translateProvider) {
    $translateProvider
        .useStaticFilesLoader({
            prefix: 'lang/',
            suffix: '.json'
        })

        .registerAvailableLanguageKeys(['en', 'ja', 'es'], {
            'en_*': 'en',
            'ja_*': 'ja',
            'es_*': 'es',
            '*': 'es'
        })
        .determinePreferredLanguage()
        // [rcj-line-offline] regla 3c: español como idioma preferido cuando no hay elección guardada.
        // Si el usuario ya eligió un idioma (localStorage NG_TRANSLATE_LANG_KEY) esa elección gana.
        .preferredLanguage('es')
        .useSanitizeValueStrategy('escape')
        .useMissingTranslationHandlerLog()
        .useLocalStorage();

}]);
