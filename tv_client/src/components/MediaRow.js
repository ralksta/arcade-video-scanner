import PropTypes from 'prop-types';

import MediaCard, {MoreCard} from './MediaCard';
import css from './Home.module.less';

// Kachelbreite in 4K-Pixeln: 680 ergibt auf Full HD 340 px — gut fünf
// Kacheln pro Reihe, die sechste angeschnitten als Hinweis, dass es weitergeht.
const CARD_WIDTH = 680;

/**
 * Eine waagerechte Reihe von Kacheln mit Überschrift.
 *
 * @param {string} title - Überschrift
 * @param {Object[]} items - Medieneinträge aus /api/videos
 * @param {Function} cardProps - (video) => {src, title, meta}
 * @param {Function} onSelect - bekommt den gewählten Eintrag
 * @param {string} [emptyText] - Hinweis, wenn die Reihe leer ist; ohne ihn
 *   entfällt die Reihe ganz
 * @param {number} [limit] - höchstens so viele Kacheln, danach „Alle anzeigen“
 * @param {Function} [onMore] - öffnet die ganze Liste; ohne ihn keine Mehr-Kachel
 * @param {string} [dotColor] - Farbpunkt vor dem Titel (Collections)
 */
const MediaRow = ({title, items, cardProps, onSelect, emptyText, limit, onMore, dotColor}) => {
	if (!items.length && !emptyText) return null;
	const shown = limit ? items.slice(0, limit) : items;

	return (
		<section className={css.row}>
			<h2 className={css.rowTitle}>
				{dotColor ? <span className={css.dot} style={{background: dotColor}} /> : null}
				{title}
				{items.length ? <span className={css.rowCount}>{items.length}</span> : null}
			</h2>
			{items.length ? (
				<div className={css.rail}>
					{shown.map(v => (
						<MediaCard
							key={v.FilePath}
							width={CARD_WIDTH}
							onSelect={() => onSelect(v)}
							{...cardProps(v)}
						/>
					))}
					{onMore ? <MoreCard width={CARD_WIDTH} total={items.length} onSelect={onMore} /> : null}
				</div>
			) : (
				<div className={css.empty}>{emptyText}</div>
			)}
		</section>
	);
};

MediaRow.propTypes = {
	cardProps: PropTypes.func.isRequired,
	items: PropTypes.array.isRequired,
	onSelect: PropTypes.func.isRequired,
	title: PropTypes.string.isRequired,
	dotColor: PropTypes.string,
	emptyText: PropTypes.string,
	limit: PropTypes.number,
	onMore: PropTypes.func
};

export default MediaRow;
