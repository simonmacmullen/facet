var facetApp = angular.module('facetApp', ['ngRoute']);

facetApp.config(['$routeProvider',
  function($routeProvider) {
    $routeProvider.
      when('/images', {
        templateUrl: 'partials/image-list.html',
        controller: 'ImageListCtrl'
      }).
      when('/images/:imageId', {
        templateUrl: 'partials/image-detail.html',
        controller: 'ImageDetailCtrl'
      }).
      otherwise({
        redirectTo: '/images'
      });
  }]);

facetApp.controller('ImageListCtrl', function ($scope, $http) {
    $http.get('json/db.json').success(function(data) {
        $scope.pix = data;
    });
});

facetApp.controller('ImageDetailCtrl', function ($scope, $http, $routeParams) {
    $http.get('json/db.json').success(function(data) {
        $scope.pic = data[$routeParams.imageId];
    });
});
