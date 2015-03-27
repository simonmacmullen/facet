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
    var do_groups = function () {
        $scope.groups = group_by_day($scope.groups_raw, $scope.group_mode);
    }
    JsonHttp.get(path, function(data) {
        $scope.meta = data.meta;
        $scope.groups_raw = data.images;
        $scope.mode = $routeParams.mode;
        do_groups();
    });

    $scope.group_mode = 'forever';
    $scope.change_group_mode = function() {
        var gm = $scope.group_mode;
        switch (gm) {
            case 'forever': gm = 'year';    break;
            case 'year':    gm = 'month';   break;
            case 'month':   gm = 'day';     break;
            case 'day':     gm = 'forever'; break;
        }
        $scope.group_mode = gm;
        do_groups();
    };
});

facetApp.controller('DetailCtrl', function ($scope, JsonHttp, $routeParams) {
    JsonHttp.get('id/' + $routeParams.imageId, function(data) {
        $scope.image = data;
    });
});

facetApp.directive('toppanel', function($rootScope) {
    return {
        restrict: 'E',
        replace: true,
        transclude: true,
        scope: { title:'@' },
        link: function(scope, element, attrs) {
            attrs.$observe('title', function(value) {
                $rootScope.title = value + " - Facet image viewer";
            });
        },
        template: '<header>' +
            '<h1><b>{{title}}</b> - Facet image viewer</h1>' +
            '<nav>' +
            '<a href="#/keywords">All keywords</a>' +
            '<a href="#/months">All months</a>' +
            '<ng-transclude></ng-transclude>' +
            '</nav>' +
            '</header>'
    };
});

facetApp.directive('logFontSize', function() {
    return {
        restrict: 'A',
        link: function(scope, element, attrs) {
            var s = Math.max(Math.log10(attrs.logFontSize), 0.8);
            element.attr("style", "font-size: " + s + "em;");
        }
    };
});

facetApp.directive('groupHeading', function() {
    return {
        restrict: 'E',
        replace: true,
        scope: { group: '=' },
        template: '<h2 ng-switch on="group.first_date.getTime() == group.last_date.getTime()">' +
            '<span ng-switch-when="true">{{group.last_date | date}}</span>' +
            '<span ng-switch-default>{{group.first_date | date}} - {{group.last_date | date}}</span>' +
            '</h2>'
    };
});

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

function group_by_day(ungrouped, group_mode) {
    var result = [];
    var date = null;
    var current;
    for (var i = 0; i < ungrouped.length; i++) {
        var d = new Date(ungrouped[i].taken);
        d = new Date(d.getFullYear(), d.getMonth(), d.getDate());
        var d2 = new Date(d.getFullYear(),
                          (group_mode == 'year') ? 0 : d.getMonth(),
                          (group_mode == 'day')  ? d.getDay() : 1);
        if (date == null ||
            (group_mode != 'forever' && date.getTime() != d2.getTime())) {
            date = d2;
            current = {last_date:d, first_date:null, images:[]};
            result.push(current);
        }
        current.images.push(ungrouped[i]);
        current.first_date = d;
    }
    return result;
}
