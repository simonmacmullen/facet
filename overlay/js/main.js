var facetApp = angular.module('facetApp', []);

facetApp.controller('FacetListCtrl', function ($scope, $http) {
    $http.get('db.json').success(function(data) {
        $scope.pix = data;
    });
});
