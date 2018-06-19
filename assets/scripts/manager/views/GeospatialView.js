define([
    'backbone.stickit',
    './BaseView',
    '../hb_templates/geospatial.hbs'
], function(stickit, BaseView, hb_template) {
        var view = BaseView.extend({
        template : hb_template,

        bindings : {
            '#country-input' : 'country',
            '#state-input' : 'state',
            '#county-input' : 'county',
            '#city-input' : 'city',
            '#otherGeospatial-input' : 'otherGeospatial',
            '#geographicExtents-input' : 'geographicExtents'
        },

        render : function() {
            BaseView.prototype.render.apply(this, arguments);
            this.stickit();
            return this;
        }
    });

    return view;
});
