// fix jQuery document.ready in _footer.js triggers the "onload" events instead of "load"

$(document)
	.on('onload', '#newUpdate-div', function () {
		getUserFavList();
		showUpdated();
	});


// logging

$(document).on('click', 'a[data-log-action]', function () {
	const $link = $(this);
	sysUserActLog($link.data('logAction'), $link.data('logSection'), '');
});


// fix html lang attribute

document.addEventListener('DOMContentLoaded', () => {
	const csdi_lang = localStorage["csdi-lang"] != null ? localStorage["csdi-lang"] : "en";
	$('html').prop('lang', csdi_lang);
	//$('html').prop('lang', $('#idUserLang').text());
});


// find scrollbar width

document.addEventListener('DOMContentLoaded', () => {
	const el = document.createElement( 'div' );

	Object.assign( el.style, {
		border: '0',
		height: '100px',
		left: '-100px',
		overflow: 'scroll',
		padding: '0',
		position: 'absolute',
		top: '-100px',
		visibility: 'hidden',
		width: '100px',
	} );

	document.body.appendChild( el );

	const scrollbarWidth = el.offsetWidth - el.clientWidth;

	document.body.removeChild( el );

	document.documentElement.classList.add( scrollbarWidth > 0 ? 'classic-scrollbars' : 'overlay-scrollbars' );
	document.documentElement.style.setProperty( '--width--scrollbar', scrollbarWidth );
});


// site nav / site menu / site notification

$(document)
	.on('click', '.site-nav__menu button', function () {
		tigger_menu();
		const expanded = $('#csdi-top-nav').is(':visible');
		$(this).prop('ariaExpanded', expanded);
		$('.site-menu__close').prop('ariaExpanded', expanded)
	})

	.on('click', '.site-nav__map a', function () {
		sessionStorage.setItem('fr', 'landingpage'); // instead of go_menu_item()
	})

	.on('click', '.site-nav__lang button, .site-menu__lang button', function () {
		close_top_nav();
		changeLang($(this).data('lang'));
	})

	.on('click', '.site-nav__logout button, .site-menu__logout', function () {
		logout();
	})

	.on('click', '.site-menu__close, .site-menu a', function () {
		close_top_nav();
		$('.site-nav__menu button').prop('ariaExpanded', false);
		$('.site-menu__close').prop('ariaExpanded', false);
	})

	// close_top_nav() is called for these events in _footer.js
	.on('click touchstart wheel', '#app', function () {
		$('.site-nav__menu button').prop('ariaExpanded', false);
		$('.site-menu__close').prop('ariaExpanded', false);
	})

	.on('click', '.site-notification__close', function () {
		$(this)
			.closest('.site-notification').addClass('hidden').end()
			.prop('ariaExpanded', false);
		sessionStorage.setItem($(this).attr('aria-controls'), 'false');
	});

document.addEventListener('DOMContentLoaded', () => {
	let updateId;

	const update = () => {
		const $button = $('.site-nav__menu button');
		if (!$button.is(':visible')) {
			close_top_nav();
			$button.prop('ariaExpanded', false);
			$('.site-menu__close').prop('ariaExpanded', false);
		}
	};

	$(window).on('resize', () => {
		clearTimeout(updateId);
		updateId = setTimeout(
			() => {
				updateId = null;
				update();
			},
			100
		);
	});

	// don't call update() here as the menu isn't loaded yet
});


// back to top

$(document).on('click', '.back-to-top', function (e) {
	e.preventDefault();
	window.scrollTo({ top: 0 });
	$(this.hash).trigger('focus');
});

document.addEventListener('DOMContentLoaded', () => {
	const $window = $(window);
	const $body = $('body');
	let updateId;

	const scheduleUpdate = () => {
		clearTimeout(updateId);
		updateId = setTimeout(
			() => {
				updateId = null;
				update();
			},
			100
		);
	};

	const update = () => {
		$body.toggleClass('show-back-to-top', $window.scrollTop() > $window.height());
	};

	$window.on('scroll', scheduleUpdate);
	update();
});


// highlight section

$(document).on('click', '.can-expand .highlight-section__expand', function () {
	const $button = $(this);
	const $section = $button.closest('.highlight-section');
	$section.toggleClass('expand');
	$button.prop('ariaExpanded', $section.hasClass('expand'));
});

$(window).on('load', () => {
	let updateId;

	const update = () => {
		$('.highlight-section').each(function () {
			const $section = $(this);
			const $button = $section.find('.highlight-section__expand');
			const $grid = $section.find('.card-grid');
			const numPreviewRows = parseInt($grid.css('--card-grid--num-preview-rows'), 10);

			if (!($button.length && $grid.length && numPreviewRows > 0)) {
				$section.removeClass('can-expand');
				return;
			}

			$grid.css({
				height: $grid.height(),
				opacity: 0,
				overflow: 'hidden'
			});

			$section.removeClass('can-expand');

			const numRows = $grid.css('grid-template-rows').split(' ').length;

			$section.toggleClass('can-expand', numRows > numPreviewRows);

			$grid.css({
				height: '',
				opacity: '',
				overflow: ''
			});
		});
	};

	const expand = (hash) => {
		if (hash.length < 2) {
			return;
		}

		const $el = $(hash);
		const $button = $el.find('.highlight-section__expand');

		if (!($el.is('.highlight-section') && $button.length)) {
			return;
		}

		$el.addClass('expand');
		$button.prop('ariaExpanded', true);
	};

	if (!$('.highlight-section__expand').length) {
		return;
	}

	$(window).on({
		resize: () => {
			clearTimeout(updateId);
			updateId = setTimeout(
				() => {
					updateId = null;
					update();
				},
				100
			);
		},
		hashchange: () => {
			expand(location.hash);
		}
	});

	$(document).on('click', 'a', function () {
		if (this.origin === location.origin &&
				this.pathname === location.pathname &&
				this.search === location.search &&
				(this.target === '' || this.target === '_self')) {
			expand(this.hash);
		}
	});

	update();
	expand(location.hash);
});


// api doc selector

$(document).on('change', '.api-doc-selector', function () {
	const selector = '.' + $(this).val();
	$('.api-doc')
		.not(selector).hide().end()
		.filter(selector).show();
});

document.addEventListener('DOMContentLoaded', () => {
	$('.api-doc-selector').trigger('change');
});


// carousel

$(document)
	.on('slide.bs.carousel', '.carousel', function () {
		$(this).find('video').each(function () { this.pause(); });
	})
	.on('slid.bs.carousel', '.carousel', function (e) {
		$(this).find('video').each(function () {
			if ($(this).data('carouselPlayFromStart')) {
				this.currentTime = 0;
			}
		});
		$(e.relatedTarget).find('video').each(function () { this.play(); });
	})
	.on('visibilitychange', function () {
		const isHidden = document.visibilityState === 'hidden';

		$(isHidden ? '.carousel.playing' : '.carousel.auto-paused')
			.carousel(isHidden ? 'pause' : 'cycle')
			.removeClass(isHidden ? 'playing' : 'paused auto-paused')
			.addClass(isHidden ? 'paused auto-paused' : 'playing');

		$('.carousel-item.active video').each(
			isHidden ?
				function () { this.pause(); } :
				function () { this.play(); }
		);
	})
	.on('click', '.carousel-toggle', function () {
		const $carousel = $($(this).data('bsTarget'));

		if (!$carousel.length) {
			return;
		}

		const isPlaying = $carousel.hasClass('playing');
		$carousel
			.carousel(isPlaying ? 'pause' : 'cycle')
			.removeClass(isPlaying ? 'playing' : 'paused')
			.addClass(isPlaying ? 'paused' : 'playing');
	});

document.addEventListener('DOMContentLoaded', () => {
	$('.carousel:not(.playing)').addClass('paused');
});

$(window).on('load', () => {
	$('.carousel.playing').carousel('cycle');

	if (document.visibilityState === 'visible') {
		$('.carousel-item.active video').each(function () { this.play(); });
	}
});


// tabs

$(document)
	.on('show.bs.tab', 'button[data-bs-toggle="tab"], button[data-bs-toggle="pill"]', function () {
		const src = $(this).data('pageHeaderImage');
		if (src) {
			$('.page__header-image img').prop('src', src);
		}
	})
	.on('shown.bs.tab', 'button[data-bs-toggle="tab"], button[data-bs-toggle="pill"]', function () {
		const trackHistory = $(this).data('trackHistory');
		if (trackHistory === false || trackHistory === 0) {
			return;
		}
		const hash = String($(this).data('bsTarget')).replace('#pane-', '#');
		if (location.hash !== hash) {
			history.pushState(null, '', hash);
		}
	});

$(window).on('hashchange.bs.tab', function () {
	if (location.hash.length > 1) {
		const bsTarget = `[data-bs-target="#pane-${location.hash.substring(1)}"]`;
		$(`button[data-bs-toggle="tab"]${bsTarget}, button[data-bs-toggle="pill"]${bsTarget}`).tab('show');
	}
});

document.addEventListener('DOMContentLoaded', () => {
	if (location.hash.length > 1) {
		$(window).trigger('hashchange.bs.tab');
	} else {
		const $pane = $('.tab-pane.active');
		if ($pane.length) {
			history.replaceState(null, '', '#' + $pane.prop('id').replace('pane-', ''));
		}
	}
});


// home page search

/*$(document)
	.on('keyup', '.page-home .catalog-search .form-control', function () {
		const $field = $(this);
		clearTimeout($field.data('timeoutId'));
		$field.data(
			'timeoutId',
			setTimeout(
				() => {
					const prev = $field.data('query') || '';
					const cur = $field.val().trim();
					$field.removeData('timeoutId');
					if (cur !== prev) {
						$field.data('query', cur);
						fnSearchResult();
					}
				},
				200
			)
		);
	})

	.on('focusin', '.page-home .catalog-search', function () {
		$(this).data('isFocus', true);
		$('#searchResult-container').show();
	})

	.on('focusout', '.page-home .catalog-search', function () {
		const $form = $(this);
		$form.data('isFocus', false);
		setTimeout(
			() => {
				if (!$form.data('isFocus')) {
					$('#searchResult-container').hide();
				}
			},
			1
		);
	});

// remove event handlers set in home.js
$(() => {
	$('.page-home #welcome_search').off('focusin focusout keydown keyup');
});*/


// home page sidebar

$(document).on('click', '.page-home__sidebar-button', function () {
	const $button = $(this);
	const $page = $button.closest('.page');
	$page.toggleClass('show-sidebar');
	$button.prop('ariaExpanded', $page.hasClass('show-sidebar'));
});


// count up animation

$(window).on('load', () => {
	$('.count-up').each(function () {
		const $el = $(this);
		const endText = $el.text().trim();
		const endNum = parseFloat(endText.replaceAll(',', ''));
		const useGrouping = endText.includes(',');
		const numFractionDigits = ((/\.(\d+)/.exec(endText) || [])[1] || '').length;
		const interval = parseFloat($el.data('interval')) || 2000;
		const numberFormat = new Intl.NumberFormat('en-us', {
			maximumFractionDigits: numFractionDigits,
			minimumFractionDigits: numFractionDigits,
			useGrouping,
		});
		let startTime;

		if (isNaN(endNum) || interval < 0) {
			$el.addClass('show');
			return;
		}

		const start = () => {
			$el
				.css('width', $el.width())
				.text(numberFormat.format(0))
				.addClass('show');

			startTime = performance.now();

			scheduleUpdate();
		}

		const scheduleUpdate = () => {
			window.requestAnimationFrame(update);
		};

		const update = () => {
			const elapsedTime = performance.now() - startTime;

			if (elapsedTime >= interval) {
				$el
					.text(endText)
					.css('width', '');
				return;
			}

			const curNum = endNum * elapsedTime / interval;
			$el.text(numberFormat.format(curNum));

			scheduleUpdate();
		};

		const observer = new IntersectionObserver(
			(entries) => {
				entries.forEach((entry) => {
					if (entry.isIntersecting) {
						observer.disconnect();
						start();
					}
				});
			},
			{
				threshold: 0.5,
			}
		);
		observer.observe(this);
	});
});


// expandable

$(document)
	.on('click', '.expandable__control', function () {
		const $button = $(this);
		const $expandable = $button.closest('.expandable');
		$expandable.toggleClass('expandable--expand');
		$button.prop('ariaExpanded', $expandable.hasClass('expandable--expand'));
	});

$(window).on('load', () => {
	let updateId;

	const update = () => {
		$('.expandable--text').each(function () {
			const $expandable = $(this);
			const $content = $expandable.children('.expandable__content');
			const height = $expandable.css('height');
			const isExpand = $expandable.hasClass('expandable--expand');

			$expandable
				.css({
					height,
					overflow: 'hidden',
				})
				.removeClass('expandable--expanded expandable--expand');

			const isExpanded = $content[0].scrollHeight <= $content[0].clientHeight;

			$expandable
				.css({
					height: '',
					overflow: '',
				})
				.toggleClass('expandable--expanded', isExpanded)
				.toggleClass('expandable--expand', isExpand);
		});

		$('.expandable--list').each(function () {
			const $expandable = $(this);
			const numItems = $expandable.find('> .expandable__content > *').length;
			const limit = parseInt(this.dataset.expandableLimit, 10);
			const isExpanded = numItems <= limit;

			$expandable.toggleClass('expandable--expanded', isExpanded);
		});
	};

	$(window).on('resize.expandable', () => {
		clearTimeout(updateId);
		updateId = setTimeout(
			() => {
				updateId = null;
				update();
			},
			100
		);
	});

	update();
});


// dataset detail section

$(document).on('click', '.can-expand .dataset-detail-section__expand', function () {
	const $button = $(this);
	const $section = $button.closest('.dataset-detail-section');
	$section.toggleClass('expand');
	$button.prop('ariaExpanded', $section.hasClass('expand'));
});


// write text to clipboard

(function (window, document) {
	const fallback = (text) => {
		const activeElement = document.activeElement;
		const textarea = document.createElement('textarea');
		let result = false;

		textarea.className = 'visually-hidden';
		textarea.value = text;

		document.body.appendChild(textarea);
		textarea.focus();
		textarea.select();
		try {
			result = document.execCommand('copy');
		} catch (error) {
			result = false;
		}
		document.body.removeChild(textarea);

		if (activeElement) {
			activeElement.focus();
		}

		return result;
	};

	window.writeTextToClipboard = (text) => new Promise((resolve, reject) => {
		if (!window.navigator.clipboard || !window.isSecureContext) {
			if (fallback(text)) {
				resolve();
			} else {
				reject();
			}
			return;
		}

		window.navigator.clipboard.writeText(text).then(
			resolve,
			() => {
				if (fallback(text)) {
					resolve();
				} else {
					reject();
				}
			}
		);
	});
})(window, document);
