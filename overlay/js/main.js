var facetApp = angular.module('facetApp', ['ngRoute']);

facetApp.config(['$routeProvider',
  function($routeProvider) {
    $routeProvider.
      when('/images', {
        templateUrl: 'partials/image-index.html',
        controller: 'IndexCtrl'
      }).
      when('/images/:indexId', {
        templateUrl: 'partials/image-list.html',
        controller: 'ListCtrl'
      }).
      when('/image/:imageId', {
        templateUrl: 'partials/image-detail.html',
        controller: 'ImageDetailCtrl'
      }).
      otherwise({
        redirectTo: '/images'
      });
  }]);

facetApp.controller('IndexCtrl', function ($scope, $http) {
    $http.get('json/index.json').success(function(data) {
        $scope.months = data.months;
        $scope.keywords = data.keywords;
    });
});

facetApp.controller('ListCtrl', function ($scope, $http, $routeParams) {
    $http.get('json/' + $routeParams.indexId + '.json').success(function(data) {
        $scope.images = data;
    });
});

facetApp.controller('ImageDetailCtrl', function ($scope, $http, $routeParams) {
    $http.get('json/db.json').success(function(data) {
        $scope.image = data[$routeParams.imageId];
    });
});
