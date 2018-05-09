/**
 * This file contains all necessary Angular controller definitions for 'frontend.login-history' module.
 *
 * Note that this file should only contain controllers and nothing else.
 */
(function () {
  'use strict';

  angular.module('frontend.apis')
    .controller('ApiDetailsController', [
      '$scope', '$rootScope', '$log', '$state', 'ApiService', '$uibModal', 'MessageService', 'SettingsService',
      function controller($scope, $rootScope, $log, $state, ApiService, $uibModal, MessageService, SettingsService) {

        var availableFormattedVersion = ApiService.getLastAvailableFormattedVersion($rootScope.Gateway.version);
        $scope.settings = SettingsService.getSettings();
        $scope.partial = 'js/app/apis/partials/form-api-' + availableFormattedVersion + '.html?r=' + Date.now();

        $scope.updateApi = function () {
          if (!$scope.api.hosts && !$scope.api.uris && !$scope.api.methods) {
            MessageService.error("Submission failed. Make sure you have completed all required fields.")
            return false;
          }

          if (!$scope.api.retries) {
            $scope.api.retries = 0
          }

          if (!$scope.api.upstream_connect_timeout) {
            $scope.api.upstream_connect_timeout = 0
          }

          if (!$scope.api.upstream_send_timeout) {
            $scope.api.upstream_send_timeout = 0
          }

          if (!$scope.api.upstream_read_timeout) {
            $scope.api.upstream_read_timeout = 0
          }

          $scope.loading = true
          ApiService.update($scope.api)
            .then(function (res) {
              $log.debug("Update Api: ", res)
              $scope.loading = false
              MessageService.success('API updated successfully!')
            }).catch(function (err) {
            console.log("err", err)
            $scope.loading = false
            var errors = {}
            Object.keys(err.data.body).forEach(function (key) {
              MessageService.error(key + " : " + err.data.body[key])
            })
            $scope.errors = errors
          })

        }

      }
    ])
  ;
}());
