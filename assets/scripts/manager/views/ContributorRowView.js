define([
    'loglevel',
    'underscore',
    'jquery',
    'select2',
    'backbone.stickit',
    '../utils/DynamicSelect2',
    './BaseView',
    '../hb_templates/contributorTabRow.hbs',
    '../hb_templates/contributorTabRowOption.hbs'
], function(log, _, $, select2, stickit, DynamicSelect2, BaseView, hb_template, optionTemplate) {
    var view = BaseView.extend({

        bindings : {
            '.affiliation-input' : {
                observe : 'affiliations',
                onGet : function(value) {
                    var displayText;
                    if (value && value.length > 0) {
                        var stagingText = _.pluck(value, 'text');
                        displayText = stagingText.join(', ');
                    } else {
                        displayText = '';
                    }
                    return displayText;
                }
            }
        },

        events : {
            'select2:select .contributor-type-input' : 'selectType',
            'select2:select .contributor-name-input' : 'selectName',
            'click .delete-row' : 'deleteRow',
            'click .edit-contributor-link' : 'clickEditLink',
            'updateOrder .contributor-row-container' : 'updateOrder'
        },

        template : hb_template,

        optionTemplate : optionTemplate,

        /*
         * @constructs
         * @param {Object} options
         *     @prop {String} el - jquery selector where view will be rendered
         *     @prop {PublicationContributorModel} model
         *     @prop {PublicationContributorCollection} collection
         */
        initialize : function() {
            BaseView.prototype.initialize.apply(this, arguments);

            this.context.contributorId = this.model.get('contributorId');
            this.context.scriptRoot = window.CONFIG.scriptRoot;

            this.listenTo(this.model, 'change:corporation', this.updateType);
            this.listenTo(this.model, 'change:text', this.updateName);
            this.listenTo(this.model, 'sync', this.updateRow);
        },

        render : function() {
            var self = this;
            var DEFAULT_SELECT2_OPTIONS = {
                theme : 'bootstrap'
            };
            BaseView.prototype.render.apply(this, arguments);

            this.stickit();

            //Initialize select2's
            this.$('.contributor-type-input').select2(DEFAULT_SELECT2_OPTIONS);
            this.updateType();

            this.$('.contributor-name-input').select2(DynamicSelect2.getSelectOptions({
                lookupType: function () {
                    return self.model.get('corporation') ? 'corporations' : 'people';
                }
            }, _.extend({minimumInputLength: 2}, DEFAULT_SELECT2_OPTIONS)));
            this.updateName();
            return this;
        },

        /*
         * DOM Event handlers
         */
        selectType : function(ev) {
            this.model.set('corporation', ev.currentTarget.value === 'corporations');
        },

        selectName : function(ev) {
            this.model.set('contributorId', ev.currentTarget.value);
            this.model.fetch();
        },

        updateOrder : function(ev, newIndex) {
            log.debug('In updateOrder: contributor ' + this.model.get('text') + ', newRank ' + (newIndex + 1));
            this.collection.updateModelRank(this.model, newIndex + 1);
        },

        deleteRow : function() {
            log.debug('Delete contributor ' + this.model.get('text'));
            this.collection.remove(this.model);
        },

        clickEditLink : function() {
            var h = window.location.protocol + '//' + window.location.hostname + ':' + window.location.port + window.location.pathname + '#contributor' +
                    (this.model.has('contributorId') ? '/' + this.model.get('contributorId') : '');
            window.open(h, '_blank');
        },

        /*
         * Model event handlers
         */

        updateType : function() {
            var $select = this.$('.contributor-type-input');
            var corporation = this.model.get('corporation');
            if (corporation) {
                $select.val('corporations').trigger('change');
            } else {
                $select.val('people').trigger('change');
            }
        },

        updateName : function() {
            var $select = this.$('.contributor-name-input');
            var id = this.model.get('contributorId');

            if (id) {
                if ($select.find('option[value="' + id + '"]').length === 0) {
                    $select.append(this.optionTemplate(this.model.attributes));
                }
                $select.val(this.model.get('contributorId')).trigger('change');
            } else {
                $select.val('').trigger('change');
            }
        }
    });

    return view;
});
