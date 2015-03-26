var facetApp = angular.module('facetApp', ['ngRoute']);

facetApp.config(['$routeProvider',
  function($routeProvider) {
    $routeProvider.
      when('/keywords', {
        templateUrl: 'partials/keywords.html',
        controller: 'MetaCtrl'
      }).
      when('/months', {
        templateUrl: 'partials/months.html',
        controller: 'MetaCtrl'
      }).
      when('/images/:mode/:indexId', {
        templateUrl: 'partials/list.html',
        controller: 'ListCtrl'
      }).
      when('/image/:imageId', {
        templateUrl: 'partials/detail.html',
        controller: 'DetailCtrl'
      }).
      otherwise({
        templateUrl: 'partials/months.html',
        controller: 'IndexCtrl'
      });
  }]);

facetApp.controller('IndexCtrl', function ($scope, JsonHttp, $window) {
    JsonHttp.get('index', function(data) {
        $window.location.href = '#/images/month/' + data.months[0].id;
    });
});

facetApp.controller('MetaCtrl', function ($scope, JsonHttp) {
    JsonHttp.get('index', function(data) {
        $scope.months = data.months;
        $scope.keywords = data.keywords;
    });
});

facetApp.controller('ListCtrl', function ($scope, JsonHttp, $routeParams) {
    var path = $routeParams.mode + '/' + $routeParams.indexId;
    JsonHttp.get(path, function(data) {
        $scope.meta = data.meta;
        $scope.images = data.images;
        $scope.mode = $routeParams.mode;
    });
});

facetApp.controller('DetailCtrl', function ($scope, JsonHttp, $routeParams) {
    JsonHttp.get('id/' + $routeParams.imageId, function(data) {
        $scope.image = data;
    });
});

facetApp.directive('toppanel', function(){
    return {
        restrict: 'E',
        transclude: true,
        scope: { title:'@' },
        template: '<header>' +
            '<h1><b>{{title}}</b> - Facet image viewer</h1>' +
            '<nav>' +
            '<a href="#/keywords">All keywords</a>' +
            '<a href="#/months">All months</a>' +
            '<ng-transclude></ng-transclude>' +
            '</nav>' +
            '</header>'
    };
})

facetApp.service('JsonHttp', function($http) {
    this.get = function(path, onsuccess) {
        return $http.get('json/' + path + '.json')
            .success(onsuccess)
            .error(function (data, status, headers, config) {
                // TODO
                //alert("Error " + status);
            });
    }
});
