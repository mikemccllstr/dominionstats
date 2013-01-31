function WeightAllTurnsSame(x_val) {
  return 1;
}

function WeightProportionalToAccumDiff(x_val) {
  return x_val;
};

function DisplayCardData(card_names_str, graph_name, weight_func) {
  function GrabDataIntoSeries(card) {
    var card_stat = all_card_data.card_stats[card];
    var total_games_available = card_stat.available;
    var point_data = card_stat[graph_name];
    var series = [];
    keys = [];
    for (var diff in point_data) {
      keys.push(diff);
    }
    keys.sort(function(a, b) { return a - b; });
    var quality = 0;
    for (var i = 0; i < keys.length; ++i) {
      var mean_var_stat = MeanVarStat(point_data[keys[i]], SimpleWinPrior());
      var std_dev = mean_var_stat.SampleStdDev() * 2;
      if (mean_var_stat.Freq() > 50 && std_dev < .1) {
	series.push([keys[i],
		     mean_var_stat.Mean(),
		     std_dev
		    ]);
      }
      var prob = mean_var_stat.Freq() / total_games_available;
      // consider subtracting out a standard dev or two to prevent
      // over-fitting.
      var goodness = mean_var_stat.Mean() - 1.0;
      var weight = weight_func(keys[i]);
      quality += prob * goodness * weight;
    }

    var point_opts = {
      errorbars: "y",
      yerr: {
	show: true, upperCap: '-', lowerCap: '-'
      }
    };

    return {label: card, points: point_opts, data: series, quality: quality};
  };

  function MinOfSeries(series) {
    var mn = 500;
    for (var i = 0; i < series.length; ++i) {
      mn = Math.min(mn, series[i][1] - series[i][2]);
    }
    return mn;
  };

  function MaxOfSeries(series) {
    var mx = -1;
    for (var i = 0; i < series.length; ++i) {
      mx = Math.max(mx, series[i][1] + series[i][2]);
    }
    return mx;
  };

  var series_list = [];
  var card_names = ExpandCardGlob(card_names_str);
  for (var i = 0; i < card_names.length; ++i) {
  if (all_card_data.card_stats[card_names[i]]) {
    series_list.push(GrabDataIntoSeries(card_names[i]));
  } else {
    console.log('bogus ' + card_names[i]);
    // handle bogus card name?
    }
  }

  series_list.sort(function(a, b) {
		     return b.quality - a.quality;
		   });

  var mn = 5000;
  var mx = -1;
  for (var i = 0; i < series_list.length; ++i) {
    mn = Math.min(MinOfSeries(series_list[i].data), mn);
    mx = Math.max(MaxOfSeries(series_list[i].data), mx);
  }

  var range = mx - mn;
  var fraction_buffer = .05;

  $.plot($("#placeholder"),
	 series_list,
	 {   xaxis: { },
	     yaxis: {  min: mn - range * fraction_buffer,
		       max: mx + range * fraction_buffer
		    },
	     legend: { position: 'se' }
	 }
  );
};

function RefreshCardGraph(graph_type) {
  DisplayCardData($('#card_names').val(), graph_type, weight_func);
  var wl = window.location;
  var new_url = ('http://' + wl.host + wl.pathname + '?cards=' +
		 encodeURIComponent($('#card_names').val()));

  if (typeof(window.history.pushState) == 'function') {
    window.history.pushState(null, new_url, new_url);
  }

  $('#collection_info').html
  ('Total of ' + all_card_data.num_games + ' games analyzed<br>' +
   'The most recent game was on ' +
   all_card_data.max_game_id.substr(5, 8) + '<br>');
};

function DisplayUrl() {
  var wl = window.location;
  var new_url = ('http://' + wl.host + wl.pathname + '?cards=' +
		 encodeURIComponent($('#card_names').val()));
  $('#url_display').val(new_url);
  var offset = $('#getlink').offset();
  $('#url_display').css(
    { left:offset.left, top:offset.top,
      height:"25px"}
  ).show().select();
};

$(document).click(
  function (e) {
    if (e.target.id != "getlink") {
      $('#url_display').hide();
    }
  }
);

jQuery.event.add(window, "load", function() {
  InitCardGlobber().done(
    function() {
      RefreshCardGraph(graph_type);
    });
});

