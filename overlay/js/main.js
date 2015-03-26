var facetApp = angular.module('facetApp', ['ngRoute']);

facetApp.config(['$routeProvider',
  function($routeProvider) {
    $routeProvider.
      when('/meta', {
        templateUrl: 'partials/image-meta.html',
        controller: 'MetaCtrl'
      }).
      when('/images/:mode/:indexId', {
        templateUrl: 'partials/image-list.html',
        controller: 'ListCtrl'
      }).
      when('/image/:imageId', {
        templateUrl: 'partials/image-detail.html',
        controller: 'DetailCtrl'
      }).
      otherwise({
        templateUrl: 'partials/image-meta.html',
        controller: 'IndexCtrl'
      });
  }]);

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
