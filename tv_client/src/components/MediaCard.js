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
 */
const MediaCard = ({src, title, meta, width, onSelect, ...rest}) => {
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
	meta: PropTypes.string,
	src: PropTypes.string,
	width: PropTypes.number
};

export default MediaCard;
