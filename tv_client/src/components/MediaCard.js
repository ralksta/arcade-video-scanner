import {useCallback} from 'react';
import PropTypes from 'prop-types';
import Spottable from '@enact/spotlight/Spottable';
import ri from '@enact/ui/resolution';

import css from './MediaCard.module.less';

const SpottableDiv = Spottable('div');

/**
 * Kachel im Netflix-Stil: 16:9-Vorschaubild, Titel und Metadaten auf einem
 * Verlauf, beim Fokus vergrößert.
 *
 * Ersetzt `ImageItem` aus Limestone: In 140 Pixel breiten Wrappern blieb dort
 * fürs Bild ein Briefmarkenformat, und als Beschriftung stand die Dateigröße.
 *
 * @param {string} src - URL des Vorschaubilds (mit Token, siehe serverConfig)
 * @param {string} title - Anzeigename
 * @param {string} [meta] - Zweite Zeile, z. B. „12:30 · 1080p · 1.2 GB“
 * @param {number} [width] - Breite in 4K-Pixeln; ohne Angabe füllt die Kachel
 *   ihre Zelle (VirtualGridList)
 * @param {Function} onSelect - OK-Taste oder Klick
 * @param {boolean} [favorite] - Stern oben links
 * @param {string} [badge] - z. B. „4K“ oder „HD“, oben rechts
 */
const MediaCard = ({src, title, meta, width, onSelect, favorite, badge, ...rest}) => {
	// Spotlight setzt den Fokus, scrollt aber nicht zwingend mit. In einer
	// waagerechten Reihe bliebe die fokussierte Kachel sonst außer Sicht.
	const handleFocus = useCallback((ev) => {
		ev.currentTarget.scrollIntoView({block: 'nearest', inline: 'nearest', behavior: 'smooth'});
	}, []);

	const style = width ? {width: ri.scale(width) + 'px'} : {width: '100%'};

	return (
		<SpottableDiv {...rest} className={css.card} style={style} onClick={onSelect} onFocus={handleFocus}>
			<div className={css.frame}>
				{src ? <img className={css.thumb} src={src} alt="" loading="lazy" /> : null}
				<div className={css.shade} />
				{favorite ? <div className={css.favorite} aria-label="Favorit">★</div> : null}
				{badge ? <div className={css.badge}>{badge}</div> : null}
				<div className={css.text}>
					<div className={css.title}>{title}</div>
					{meta ? <div className={css.meta}>{meta}</div> : null}
				</div>
			</div>
		</SpottableDiv>
	);
};

MediaCard.propTypes = {
	onSelect: PropTypes.func.isRequired,
	title: PropTypes.string.isRequired,
	badge: PropTypes.string,
	favorite: PropTypes.bool,
	meta: PropTypes.string,
	src: PropTypes.string,
	width: PropTypes.number
};

/**
 * Letzte Kachel einer Reihe: öffnet die ganze Sammlung als Raster.
 *
 * @param {number} total - Gesamtzahl der Einträge
 * @param {number} [width] - Breite in 4K-Pixeln
 * @param {Function} onSelect
 */
const MoreCard = ({total, width, onSelect, ...rest}) => {
	const handleFocus = useCallback((ev) => {
		ev.currentTarget.scrollIntoView({block: 'nearest', inline: 'nearest', behavior: 'smooth'});
	}, []);
	const style = width ? {width: ri.scale(width) + 'px'} : {width: '100%'};

	return (
		<SpottableDiv {...rest} className={css.card + ' ' + css.more} style={style} onClick={onSelect} onFocus={handleFocus}>
			<div className={css.frame}>
				<div className={css.moreText}>
					Alle anzeigen →
					<div className={css.moreCount}>{total} Einträge</div>
				</div>
			</div>
		</SpottableDiv>
	);
};

MoreCard.propTypes = {
	onSelect: PropTypes.func.isRequired,
	total: PropTypes.number.isRequired,
	width: PropTypes.number
};

export {MoreCard};
export default MediaCard;
