function Round(val, places) {
  var pow = Math.pow(10, places);
  return Math.round(val * pow) / pow;
};

var card_list = null;
var keyed_cards = {};

function InitCardGlobber() {
  return $.ajax(
    {url: 'static/card_list.js',
     dataType: 'json',
     success: function(data) {
       // hack, I don't understand this, according to the
       // docs, this should be parsed for me already.
       card_list = eval(data);
       for (var i = 0; i < card_list.length; ++i) {
         keyed_cards[card_list[i].Singular] = card_list[i];
       }
     }});
};

// Requires InitCardGlobber ajax to be finished.
function IsVictory(card_name){
  return keyed_cards[card_name]['Victory'] == '1';
};

function IsReaction(card_name) {
  return keyed_cards[card_name]['Reaction'] == '1';
};

function NumActions(card_name) {
  return parseInt(keyed_cards[card_name]['Actions']) || 1;
};

function ExpandSubglob(glob) {
    var ret = [];
    try {
        // This should probably be an object to avoid the linear search.
        for (var i = 0; i < card_list.length; ++i) {
            var per_card_attrs = card_list[i];
            if (glob.trim().toLowerCase() == 
                per_card_attrs.Singular.toLowerCase()) {
                ret.push(per_card_attrs.Singular);
                return ret;
            }
        }

        for (var i = 0; i < card_list.length; ++i) {
            var per_card_attrs = card_list[i];
            if (per_card_attrs.Singular == "Archivist") {
                continue;
            }
            for (k in per_card_attrs) {
                var val = per_card_attrs[k];
                if (isNaN(parseInt(val))) {
                    eval(k + '= "' + val + '"');
                } else {
                    eval(k + '=' + val);
                }
            }
            if (eval(glob)) {
                ret.push(per_card_attrs.Singular);
            }
        }
    } catch (err) {
        console.log(err);
    }
    return ret;    
};

function ExpandCardGlob(glob) {
    // Glob is either something like "Worker's Village, Smithy" or
    // "actions==2&&cards>=1".
    var ret = [];
    var subglobs = glob.split(',');
    for (var i = 0; i < subglobs.length; ++i) {
        ret = ret.concat(ExpandSubglob(subglobs[i].trim()));
    }
    return ret;
};

if (typeof exports !== "undefined" && exports !== null) {
    exports.ExpandCardGlob = ExpandCardGlob;    
    exports.InitCardGlobber = InitCardGlobber;
}

