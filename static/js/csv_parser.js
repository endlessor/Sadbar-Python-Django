'use strict';

!function (_) {
    angular.module('app', ['ui.grid',
            'ui.grid.edit',
            'ui.grid.resizeColumns',
            'ui.grid.grouping',
            'ui.grid.cellNav',
            'ui.select',
            'ui.bootstrap',
            'angularScreenfull'])
        .config(function ($interpolateProvider) {
            $interpolateProvider.startSymbol('{[{');
                $interpolateProvider.endSymbol('}]}');
        })
    .factory('Papa', function () {
        if (typeof Papa === 'undefined') {
            throw new Error('PapaParse is undefined!');
        }
        return Papa;
    })
    .controller('CsvParseCtrl', ['$scope', 'Papa', 'uiGridConstants', '$timeout', '$uibModal','$location', '$http', function ($scope, Papa, uiGridConstants, $timeout, $uibModal,$location, $http) {

        var extColumns = [];

        $scope.type = {
            CREATE : false,
    EXTEND : false,
    MODIFY : false
        };

        $timeout(function () {
            switch (type){
                case 'extend' : $scope.type.EXTEND = true; break;
                case 'modify' : $scope.type.MODIFY = true; break;
                case 'create' : $scope.type.CREATE = true; break;
            }

            if($scope.type.MODIFY || $scope.type.EXTEND){
                var data = targetList;
            }
            if ($scope.type.CREATE) {
                $scope.gOpts.columnDefs = getUtilsCols()
            .concat(attrColDef('firstname'),
                attrColDef('lastname'),
                attrColDef('email'),
                attrColDef('timezone'))
            } else if ($scope.type.EXTEND || $scope.type.MODIFY) {
                $scope.listName = data.nickname;
                $scope.description = decodeURI(data.description);
                $scope.client = data.client.id.toString();

                var target = data.targets[0];
                if (target) {
                    var keys = _.filter(Object.keys(target), function (key) {
                        return key != 'targetDatum' && key != 'id';
                    });

                    extColumns = _.union(keys, Object.keys(target.targetDatum));

                    $scope.gOpts.columnDefs = getUtilsCols();
                    _.forEach(extColumns, function (key) {
                        var splittedKey = key.split('_');
                        if(splittedKey.length == 3) {
                            $scope.gOpts.category.push({
                                name: splittedKey[1],
                                visible: true
                            });
                            var newCol = catColDef(splittedKey[1], splittedKey[2]);
                            $scope.gOpts.columnDefs.push(newCol);
                        } else {
                            $scope.gOpts.columnDefs.push(attrColDef(key))
                        }
                    });
                }
            }

            if($scope.type.MODIFY){
                $scope.gOpts.data = _.map(data.targets, function (target) {
                    var result = _.merge(target, target.targetDatum);
                    delete result['targetDatum'];
                    result.all = true;
                    return result
                })
            }
        });

        var templates = {
            checkbox: '<div align="center"><input type="checkbox" ng-model="MODEL_COL_FIELD"></div>'
        };

        $scope.description = "";

        function catColDef(categoryName, columnName) {
            return {
                'name': categoryName + '_' + _.camelCase(columnName),
                    displayName: columnName,
                    category: categoryName,
                    enableCellEdit: false,
                    groupingShowAggregationMenu: false,
                    enableGrouping: false,
                    enableHiding: false,
                    cellTemplate: templates.checkbox,
                    menuItems: [menuItems.removeCol, menuItems.removeCat, menuItems.toAttrCol, menuItems.renameCol]
            }
        }

        var menuItems = {
            removeCol: {
                title: 'Remove Column',
                icon: 'fa fa-times',
                action: function ($event) {
                    var name = this.context.col.name;
                    var category = this.context.col.colDef.category;
                    if (name) {
                        $scope.gOpts.columnDefs.splice(_.findIndex($scope.gOpts.columnDefs, _.matchesProperty('name', name)), 1);
                        var restCols = _.filter($scope.gOpts.columnDefs, _.matchesProperty('category', category));
                        if (restCols.length == 0) {
                            $scope.gOpts.category.splice(_.findIndex($scope.gOpts.category, _.matchesProperty('name', category)), 1)
                        }
                        $scope.gOpts.data.map(function (row) {
                            delete row[name];
                            return row;
                        });
                    }
                }
            },
            removeCat:{
                title: 'Remove Category',
                icon: 'fa fa-trash',
                action: function($event){
                    var category = this.context.col.colDef.category;
                    if(confirm("Are you sure you want to remove '" + category + "' category?")){
                        var columns = _($scope.gOpts.columnDefs)
                            .filter(_.matchesProperty('category',category))
                            .map('name')
                            .value();

                        $scope.gOpts.columnDefs = _.filter($scope.gOpts.columnDefs, function (col) {
                            return col.category != category;
                        });
                        $scope.gOpts.category.splice(_.findIndex($scope.gOpts.category, _.matchesProperty('name',category)),1);

                        $scope.gOpts.data = _.map($scope.gOpts.data,function(row){
                            _.forEach(columns,function(key){
                                delete row[key];
                            });
                            return row;
                        });
                    }
                }
            },
            toCatCol: {
                title: 'to Category Column',
                icon: 'fa fa-tasks',
                action: function ($event) {
                    if (this.context.col.name) {
                        toCategoryColumn(this.context.col.name);
                    }
                }
            },
            toAttrCol: {
                title: 'to Attribute Column',
                icon: 'fa fa-key',
                action: function ($event) {
                    if (this.context.col.colDef.category) {
                        toAttrColumn(this.context.col.colDef.category);
                    }
                }
            },
            //toBooleanCol: {
            //   title: 'to Boolean Column',
            //   icon: 'ui-grid-icon-blank',
            //   action: function ($event) {
            //      var name = this.context.col.name;
            //      this.context.col.colDef.type = 'boolean';
            //      $scope.gOpts.data = _.map($scope.gOpts.data, function (row) {
            //         var lc = String.toLowerCase(row[name]);
            //         row[name] = !!(lc && lc != 'no' && lc != 'false' && lc != '' && lc != 0);
            //         return row
            //      });
            //      _.find($scope.gOpts.columnDefs, _.matchesProperty('name', name)).cellTemplate = templates.checkbox;
            //   }
            //},
            fillEmpty: {
                title: 'Fill empty values',
                icon: 'fa fa-magic',
                action: function ($event) {
                    var newVal = prompt('Enter value to fill with :');
                    var name = this.context.col.name;
                    $scope.gOpts.data = _.map($scope.gOpts.data, function (row) {
                        if(!row[name]) row[name] = '';
                        row[name] = row[name].length > 0 ? row[name] : newVal;
                        return row;
                    })
                }
            },
            renameCol: {
                title: 'Rename Column',
                icon: 'fa fa-pencil',
                action: function ($event) {
                    renameColumn(this.context.col.name,this.context.col.colDef.category);
                }
            },
            setAsFirstName : {
                title: 'Set as First Name Column',
                icon: 'fa fa-user',
                action: function ($event) {
                    if(_.find($scope.gOpts.columnDefs, _.matchesProperty('name','firstname'))){
                        alert('First Name column is already present.');
                    } else {
                        renameColumn(this.context.col.name,this.context.col.colDef.category,'firstname');
                    }
                }
            },
            setAsLastName : {
                title: 'Set as Last Name Column',
                icon: 'fa fa-user',
                action: function ($event) {
                    if(_.find($scope.gOpts.columnDefs, _.matchesProperty('name','lastname'))){
                        alert('Last Name column is already present.');
                    } else {
                        renameColumn(this.context.col.name,this.context.col.colDef.category,'lastname');
                    }
                }
            },
            setAsEmail : {
                title: 'Set as Email column',
                icon: 'fa fa-user',
                action: function ($event) {
                    if(_.find($scope.gOpts.columnDefs, _.matchesProperty('name','email'))){
                        alert('Email column is already present.');

                    }else{
                        renameColumn(this.context.col.name,this.context.col.colDef.category,'email');
                    }
                }
            },
            setAsTimezone : {
                title: 'Set as Timezone column',
                icon: 'fa fa-user',
                action: function ($event) {
                    if(_.find($scope.gOpts.columnDefs, _.matchesProperty('name','timezone'))){
                        alert('Timezone column is already present.');
                    } else {
                        renameColumn(this.context.col.name,this.context.col.colDef.category,'timezone');
                    }
                }
            }
        };

        function attrColDef (columnName) {
            var currentMenuItems = [];

            if(columnName != 'firstname' && columnName != 'lastname' && columnName != 'email'  && columnName != 'timezone' && ($scope.type.CREATE || extColumns.indexOf(columnName) < 0)){
                currentMenuItems.push(menuItems.removeCol,menuItems.renameCol);
            }

            if(columnName != 'firstname' && columnName != 'lastname' && columnName != 'email' && columnName != 'timezone' && $scope.type.CREATE){
                currentMenuItems.push(menuItems.toCatCol);
            }

            if(columnName != 'firstname' && columnName != 'lastname' && columnName != 'email' && columnName != 'timezone' && $scope.type.MODIFY) {
                currentMenuItems.push(menuItems.toCatCol, menuItems.removeCol);
            }

            currentMenuItems.push(
                menuItems.fillEmpty,
                menuItems.setAsFirstName,
                menuItems.setAsLastName,
                menuItems.setAsEmail,
                menuItems.setAsTimezone
            );

            if(columnName == 'timezone') {
                return {
                    name: _.camelCase(columnName),
                        displayName: columnName,
                        category: 'Attributes',
                        enableHiding: false,
                        groupingShowAggregationMenu: false,
                        enableGrouping: false,
                        menuItems: _.clone(currentMenuItems),
                        editType: 'dropdown',
                        editableCellTemplate: '/static/partials/ui-select.html',
                        // These options can be any pytz timezone codes.
                        editDropdownOptionsArray: ['(use client)', 'UTC-12:00', 'UTC-11:00', 'UTC-10:00', 'UTC-09:00', 'UTC-08:00', 'UTC-07:00', 'UTC-06:00', 'UTC-05:00', 'UTC-04:00', 'UTC-03:00', 'UTC-02:00', 'UTC-01:00', 'UTC+00:00', 'UTC+01:00', 'UTC+02:00', 'UTC+03:00', 'UTC+04:00', 'UTC+05:00', 'UTC+06:00', 'UTC+07:00', 'UTC+08:00', 'UTC+09:00', 'UTC+10:00', 'UTC+11:00', 'UTC+12:00', 'UTC+13:00', 'UTC+14:00']
                }
            } else {
                return {
                    name: _.camelCase(columnName),
                        displayName: columnName,
                        category: 'Attributes',
                        enableHiding: false,
                        groupingShowAggregationMenu: false,
                        enableGrouping: false,
                        menuItems: _.clone(currentMenuItems)
                }
            }
        }

        function getUtilsCols() {
            return _.clone([{
                name: 'delete',
                   displayName: '',
                   enableHiding: false,
                   category: 'Util',
                   maxWidth: 30,
                   enableCellEdit: false,
                   enableColumnMenu: false,
                   cellTemplate: '<span style="padding: 3px; cursor: pointer;" class="ui-grid-cell-contents"><i class="fa fa-times fa-2x" ng-click="grid.appScope.deleteRow(row)" style="color:red"></i></span>'
            }, {
                name: 'all',
                category: 'Util',
                cellTemplate: templates.checkbox,
                width: 50,
                type: 'boolean',
                enableHiding: false,
                enableColumnMenu: true,
                enableCellEdit: false,
                menuItems: [menuItems.removeCol]
            }])
        }

        function renameCategory (oldName, newName) {
            var cat = _.find($scope.gOpts.category, _.matchesProperty('name', oldName));
            cat.name = newName;
            _.forEach($scope.gOpts.columnDefs, function(column) {
                if(column.category == oldName) {
                    column.category = newName;
                    column.name = newName + "_" + _.camelCase(column.displayName);
                }
            });
            _.forEach($scope.gOpts.data, function(row) {
                _.forEach(row, function(val, key) {
                    var splittedKey = key.split('_');
                    if(splittedKey.length == 2) {
                        if(splittedKey[0] == oldName) {
                            delete row[key];
                            row[newName + "_" + splittedKey[1]] = val;
                        }
                    }
                })
            });
        }

        $scope.gOpts  = {
            rowHeight: 38,
            enableHiding: false,
            enableSorting: false,
            minRowsToShow: 20,
            enableCellEditOnFocus: false,
            enableColumnResizing: true,
            headerTemplate: '/static/partials/header-template.html',
            category: [{name: 'Util', visible: true}, {name: 'Attributes', visible: true}],
            onRegisterApi: function (gridApi) {
                $scope.gridApi = gridApi;
            },
            renameCategory: function(oldName) {
                var newName = _.camelCase(prompt('Enter new name'));
                if(newName)
                  renameCategory(oldName, newName);
            },
            addColumn: function(name) {
                $scope.addColumnModal(name);
            }
        };

        var renameColumn = function (oldName,category,customName) {
            var attrCol = category == 'Attributes';
            var newName = customName || _.camelCase(prompt('Enter new name for column :'));

            if(newName && newName.length > 0){
                var colIndex = _.findIndex($scope.gOpts.columnDefs, _.matchesProperty('name', oldName));
                var col = attrCol ? attrColDef(newName) : catColDef(category, newName);
                $scope.gOpts.columnDefs.splice(colIndex, 1, col);
                $scope.gridApi.core.notifyDataChange(uiGridConstants.dataChange.COLUMN);

                $scope.gOpts.data = _.map($scope.gOpts.data, function (row) {
                    row[attrCol ? newName : category + '_' + newName] = row[oldName];
                    delete row[oldName];
                    return row;
                });
            }
        };

        $scope.deleteRow = function (row) {
            var index = $scope.gOpts.data.indexOf(row.entity);
            $scope.gOpts.data.splice(index, 1);
        };

        $scope.addColumnModal = function (name) {
            var modal = $uibModal.open({
                templateUrl: '/static/partials/addColumnModal.html',
                controller: ['$scope', '$uibModalInstance', 'categories', function ($scope, $uibModalInstance, categories) {
                    $scope.categories = categories;
                    if(name) {
                        var id = -1;
                        _.forEach(categories, function(cat, key) {
                            if(cat == name) id = key;
                        });
                        $scope.columnCategory = categories[id];
                    } else {
                        $scope.columnCategory = categories[0];
                    }

                    $scope.setCategory = function (category) {
                        $scope.columnCategory = category;
                    };

                    $scope.ok = function () {
                        if ($scope.addColumnName === undefined) {
                            alert("Enter a column name.");
                        } else {
                            $uibModalInstance.close([$scope.columnCategory, $scope.addColumnName, $scope.addColumnDefault]);
                        }
                    };

                    $scope.cancel = function () {
                        $uibModalInstance.dismiss('cancel');
                    };
                }],
                resolve: {
                    categories: function () {
                        return _($scope.gOpts.category)
                            .map('name')
                            .filter(function (name) {
                                return name != 'Util'
                            }).value();
                    }
                }
            });

            modal.result.then(function (data) {
                var index = _.findLastIndex($scope.gOpts.columnDefs, _.matchesProperty('category', data[0]));
                var attrCol = data[0] == 'Attributes';
                var newCol;
                if (attrCol) {
                    newCol = attrColDef(data[1]);
                    $scope.gOpts.columnDefs.splice(index + 1, 0, newCol);
                    $scope.gOpts.data = _.map($scope.gOpts.data, function (row) {
                        row[_.camelCase(data[1])] = data[2];
                        return row;
                    })
                } else {
                    newCol = catColDef(data[0], _.camelCase(data[1]));
                    $scope.gOpts.columnDefs.splice(index + 1, 0, newCol);
                    $scope.gOpts.data = _.map($scope.gOpts.data, function (row) {
                        row[data[0] + '_' + _.camelCase(data[1])] = data[2];
                        return row;
                    })
                }
            })
        };

        $scope.addRow = function () {
            $scope.gOpts.data.push({
              all: true
            });
        };

        function toAttrColumn(categoryName) {
            var defs = _.filter($scope.gOpts.columnDefs, _.matchesProperty('category', categoryName));
            var keys = _.map(defs, 'name');
            var lastAttrIndex = _.findLastIndex($scope.gOpts.columnDefs, _.matchesProperty('category', 'Attributes')) + 1;
            $scope.gOpts.columnDefs.splice(lastAttrIndex, 0, attrColDef(categoryName));
            $scope.gOpts.data = _.map($scope.gOpts.data, function (row) {
                var possibleValue = _(row)
                .pick(function (val, key) {
                    return _.startsWith(key, categoryName) && val;
                })
            .pairs()
                .value();

                row[categoryName] = (possibleValue[0] && possibleValue[0][0].substr(categoryName.length + 1)) || '';
            _.forEach(keys, function (key) {
                delete row[key];
            });
            return row;
            });
            _.remove($scope.gOpts.columnDefs, _.matchesProperty('category', categoryName));
            $scope.gOpts.category.splice(_.findIndex($scope.gOpts.category, _.matchesProperty('name', categoryName)), 1);
        }

        function toCategoryColumn(columnName) {
            var values = _.uniq(_.map($scope.gOpts.data, function (row) {
                return row[columnName] && row[columnName].length > 0 ? row[columnName] : 'noValue';
            }));

            $scope.gOpts.data = _.map($scope.gOpts.data, function (row) {
                _.forEach(values, function (val) {
                    if (val != 'noValue') {
                        var alreadySet = row[columnName + '_' + _.camelCase(val)];
                        row[columnName + '_' + _.camelCase(val)] = alreadySet ? alreadySet : row[columnName] == val;
                    } else {
                        row[columnName + '_' + _.camelCase(val)] = row[columnName] == '';
                    }
                });
                delete row[columnName];
                return row;
            });

            $scope.gOpts.columnDefs.splice(_.findIndex($scope.gOpts.columnDefs, _.matchesProperty('name', columnName)), 1);
            values = _(values).map(_.camelCase).uniq().value();
            _.forEach(values, (function (name) {
                $scope.gOpts.columnDefs.push(catColDef(columnName, name));
            }));
            $scope.gOpts.category.push({
                name: columnName,
                visible: true
            });
        }

        function processCSV(papaResult) {
            $scope.gOpts.data = _.map(papaResult.data,
                    function (object) {
                        var row = _(object)
                .pairs()
                .map(function (arr) {
                    return [_.camelCase(arr[0]), arr[1]]
                })
            .zipObject()
                .value();
            row['all'] = true;
            return row;
                    });

            if($scope.type.CREATE){
                $scope.gOpts.columnDefs = getUtilsCols();
            }
            _.forEach(Object.keys($scope.gOpts.data[0]), function (name) {
                if (name != 'all' && extColumns.indexOf(name) < 0) {
                    $scope.gOpts.columnDefs.push(attrColDef(name));
                }
            });

            if (papaResult.data.length > 20) {
                $scope.gOpts.minRowsToShow = papaResult.data;
            }
        }

        $scope.parse = function () {
            Papa.parse($('#csv')[0].files[0],
                    {
                        worker: true,
            header: true,
            complete: function (result) {
                $scope.$apply(function () {
                    processCSV(result);
                });
            }
                    })
        };

        $scope.save = function (split, form) {
            form.listName.$setTouched();
            form.client.$setTouched();
            if(form.$invalid) {
                return false;
            }
            if (split && !$scope.splitAllControl) {
                alert('Split all control isn\'t checked! Canceled.');
                return false;
            }

            function columnExists(colName) {
                var columnInDefs = _.map($scope.gOpts.columnDefs, function (eachObject) {
                    return (eachObject.name === colName);
                });
                var columnIsPresent = columnInDefs.filter(function (eachObject) {
                    return (eachObject === true);
                }).length === 1;
                return columnIsPresent;
            }

            var errors = [];
            if(typeof $scope.gOpts.data[0].firstname === 'undefined') errors.push('firstname');
            if(typeof $scope.gOpts.data[0].lastname === 'undefined') errors.push('lastname');
            if(typeof $scope.gOpts.data[0].email === 'undefined') errors.push('email');
            // This makes it mandatory to have some data in the first target's timezone field:
            // if(typeof $scope.gOpts.data[0].timezone === 'undefined') errors.push('timezone');
            // This merely checks if the timezone field exists for the first target, which is necessary
            // when timezones are allowed to be left blank (eg, when using the Client's default timezone):
            if(!(columnExists('timezone'))) errors.push('timezone');

            var namingTip = '\n\nTip: Required columns\' names must be lower case.';
            if(errors.length) {
                if(errors.length == 1) alert('You must set the ' + errors[0] + ' column!' + namingTip);
                if(errors.length == 2) alert('You must set the ' + errors[0] + ' and ' + errors[1] + ' columns!' + namingTip);
                if(errors.length == 3) alert('You must set the ' + errors[0] + ', ' + errors[1] + ' and ' + errors[2] + ' columns!' + namingTip);
                if(errors.length == 4) alert('You must set the ' + errors[0] + ', ' + errors[1] + ', ' + errors[2] + ' and ' + errors[3] + ' columns!' + namingTip);
                return false;
            }

            var categoryKeys = _($scope.gOpts.columnDefs)
                .filter(function (col) {
                    return col.category != 'Attributes' && col.name != 'delete';
                }).map('name').value();

            var result = [];

            if (!split) {
                categoryKeys.forEach(function (key) {
                    if(key == "all") {
                        result.push({nickname: key, client: $scope.client, description: $scope.description, targets: []});
                    } else {
                        var newKey = $scope.listName + "_" + key;
                        result.push({nickname: newKey, client: $scope.client, description: $scope.description, targets: []});
                    }
                });
            }

            _.forEach($scope.gOpts.data, function (row, index) {
                var usefulData = angular.copy(row);
                _.forEach(categoryKeys, function (key) {
                    delete usefulData[key]
                });

                var seed = _.omit(usefulData, function (value, key) {
                    return (key != 'firstname' && key != 'lastname' && key != 'email' && key != 'timezone' && key != 'id')
                });

                seed['targetDatum'] = _.omit(usefulData, function (value, key) {
                    return (key == 'firstname' || key == 'lastname' || key == 'email' || key == 'timezone' || key == 'id')
                });

                if (split) {
                    result.push({
                        nickname: $scope.listName + '_' + index,
                        client : $scope.client,
                        description: $scope.description,
                        targets: [seed]
                    });
                } else {
                    _.forEach(categoryKeys, function (key) {
                        if (row[key]) {
                            var cat = '';
                            if(key != 'all') {
                                var newKey = $scope.listName + "_" + key;
                                cat = _.find(result, _.matchesProperty('nickname', newKey));
                            } else {
                                cat = _.find(result, _.matchesProperty('nickname', key));
                            }
                            if(cat) {
                                cat.client = $scope.client;
                                cat.targets.push(seed);
                            }
                        }
                    })
                }
            });

            if (!split) {
                var main = _.find(result, _.matchesProperty('nickname', 'all'));
                if(main) {
                    main.nickname = $scope.listName;
                    if(!$scope.type.CREATE)
                        main.id = targetList.id;
                    main.description = $scope.description;
                }
            }
            if($scope.type.CREATE) {
                var url = '/targets-list/add/';
            }
            if($scope.type.MODIFY) {
                var url = '/targets-list/edit/' + targetList.id + '/';
            }
            if($scope.type.EXTEND) {
                var url = '/targets-list/edit/extend/' + targetList.id + '/';
            }

            _.forEach(result, function(res, key) {
                res.description = encodeURI(res.description);
            });

            for(var i = result.length - 1; i >= 0; i--) {
                if(result[i].targets.length == 0) {
                    result.splice(i, 1);
                }
            }

            if($scope.type.MODIFY) {
                _.forEach(result, function (res, keyRes) {
                    if(!res.id) {
                        _.forEach(res.targets, function(target,keyTarget) {
                            if(target.id) delete result[keyRes].targets[keyTarget].id
                        })
                    }
                });
            }

            $.ajax({
                method: 'POST',
                url: url,
                data: {'targets': JSON.stringify(result)},
                success: function() {
                    window.location.href = "/targets-list/list/";
                }
            })
        };
    }]);
}(_);
