define([
    'backbone.stickit',
    './BaseView',
    '../hb_templates/editCorporation.hbs'
], function(stickit, BaseView, hbTemplate) {
        /*
     * @constructs
     * @param {Object} options
     *      @prop {Jquery selector} el
     *      @prop {ContributorModel} model
     */
    var view = BaseView.extend({
        template : hbTemplate,

        bindings : {
            '#organization' : 'organization'
        },

        render : function() {
            BaseView.prototype.render.apply(this, arguments);
            this.stickit();
            return this;
        }

    });

    return view;
});
