import {useCallback} from 'react';
import PropTypes from 'prop-types';
import Spottable from '@enact/spotlight/Spottable';
import ri from '@enact/ui/resolution';

import css from './CollectionTile.module.less';

const SpottableDiv = Spottable('div');

/**
 * Große Kachel für eine Collection, wie die Marken-Kacheln bei Paramount+
 * oder Disney+: Verlauf in der Farbe der Collection über einem Vorschaubild,
 * Name groß, Anzahl darunter.
 *
 * @param {string} name
 * @param {string} color - Farbe der Collection aus der Web-App
 * @param {number} count - Treffer
 * @param {string} [src] - Vorschaubild des ersten Treffers
 * @param {number} width - Breite in 4K-Pixeln
 * @param {Function} onSelect
 */
const CollectionTile = ({name, color, count, src, width, onSelect, ...rest}) => {
	const handleFocus = useCallback((ev) => {
		ev.currentTarget.scrollIntoView({block: 'nearest', inline: 'nearest', behavior: 'smooth'});
	}, []);

	return (
		<SpottableDiv
			{...rest}
			className={css.tile}
			style={{width: ri.scale(width) + 'px', '--tile-color': color}}
			onClick={onSelect}
			onFocus={handleFocus}
		>
			<div className={css.frame}>
				{src ? <img className={css.image} src={src} alt="" loading="lazy" /> : null}
				<div className={css.tint} />
				<div className={css.text}>
					<div className={css.name}>{name}</div>
					<div className={css.count}>{count === 1 ? '1 Titel' : `${count} Titel`}</div>
				</div>
			</div>
		</SpottableDiv>
	);
};

CollectionTile.propTypes = {
	color: PropTypes.string.isRequired,
	count: PropTypes.number.isRequired,
	name: PropTypes.string.isRequired,
	onSelect: PropTypes.func.isRequired,
	width: PropTypes.number.isRequired,
	src: PropTypes.string
};

export default CollectionTile;
