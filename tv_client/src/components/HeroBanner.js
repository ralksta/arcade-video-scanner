import {useState, useEffect, useRef, useCallback} from 'react';
import PropTypes from 'prop-types';
import SpotlightContainerDecorator from '@enact/spotlight/SpotlightContainerDecorator';

import PillButton from './PillButton';
import Backdrop from './Backdrop';
import css from './Home.module.less';

const ROTATE_MS = 9000;

// Von der Kopfleiste kommend landet der Fokus auf „Abspielen“ — vorher nahm
// Spotlight den geometrisch nächsten Knopf, und das war „Mehr Infos“.
const Actions = SpotlightContainerDecorator(
	{enterTo: 'default-element', defaultElement: '[data-hero-play]'},
	'div'
);

/**
 * Großes Titelbild oben auf Home, randlos bis unter die Kopfleiste — wie bei
 * Netflix und HBO. Wechselt alle neun Sekunden zum nächsten Eintrag (mit
 * Überblendung und langsamem Zoom), aber nicht, solange der Fokus auf den
 * Knöpfen liegt: Sonst spielte „Abspielen“ plötzlich etwas anderes.
 *
 * @param {Object[]} items - hervorgehobene Einträge (die ersten fünf werden gezeigt)
 * @param {Function} cardProps - (video) => {src, poster, title, meta, badge}
 * @param {string} [eyebrow] - kleine Zeile über dem Titel
 * @param {Function} onPlay - bekommt den gezeigten Eintrag
 * @param {Function} onInfo - „Mehr Infos“, bekommt den gezeigten Eintrag
 */
const HeroBanner = ({items, cardProps, eyebrow, onPlay, onInfo}) => {
	const slides = items.slice(0, 5);
	// `reached`: bis zu welchem Bild schon geladen werden darf — das gezeigte
	// und das nächste. Jedes Standbild kostet den Server beim ersten Mal einen
	// ffmpeg-Lauf, nicht fünf auf einmal beim Start.
	const [{index, reached}, setPos] = useState({index: 0, reached: 1});
	const [paused, setPaused] = useState(false);
	const sectionRef = useRef(null);

	useEffect(() => {
		if (paused || slides.length < 2) return undefined;
		const timer = setTimeout(() => setPos(pos => {
			const next = (pos.index + 1) % slides.length;
			return {index: next, reached: Math.max(pos.reached, next + 1)};
		}), ROTATE_MS);
		return () => clearTimeout(timer);
	}, [index, paused, slides.length]);

	// Fokus auf den Knöpfen: anhalten und Home ganz nach oben rollen, damit
	// das Bild wieder ganz zu sehen ist.
	const handleFocus = useCallback(() => {
		setPaused(true);
		const scroller = sectionRef.current && sectionRef.current.parentElement;
		if (scroller) scroller.scrollTo({top: 0, behavior: 'smooth'});
	}, []);
	const handleBlur = useCallback((ev) => {
		if (!sectionRef.current || !sectionRef.current.contains(ev.relatedTarget)) setPaused(false);
	}, []);

	if (!slides.length) return null;
	const current = slides[Math.min(index, slides.length - 1)];
	const props = cardProps(current);

	return (
		<section ref={sectionRef} className={css.hero} onFocus={handleFocus} onBlur={handleBlur}>
			{slides.map((v, i) => {
				if (i > reached) return null;
				const p = cardProps(v);
				return (
					<Backdrop
						key={v.FilePath}
						className={css.heroImage + (i === index ? ' ' + css.heroImageActive : '')}
						poster={p.poster}
						fallback={p.src}
					/>
				);
			})}
			<div className={css.heroShade} />
			<div className={css.heroText} key={current.FilePath}>
				{eyebrow ? <div className={css.heroEyebrow}>{eyebrow}</div> : null}
				<div className={css.heroTitle}>{props.title}</div>
				<div className={css.heroMeta}>
					{props.badge ? <span className={css.heroBadge}>{props.badge}</span> : null}
					{props.meta}
				</div>
				<Actions className={css.heroActions}>
					<PillButton variant="primary" icon="play" data-hero-play onClick={() => onPlay(current)}>Abspielen</PillButton>
					<PillButton icon="info" onClick={() => onInfo(current)}>Mehr Infos</PillButton>
				</Actions>
			</div>
			{slides.length > 1 ? (
				<div className={css.heroDots}>
					{slides.map((v, i) => (
						<span key={v.FilePath} className={css.heroDot + (i === index ? ' ' + css.heroDotActive : '')} />
					))}
				</div>
			) : null}
		</section>
	);
};

HeroBanner.propTypes = {
	cardProps: PropTypes.func.isRequired,
	items: PropTypes.array.isRequired,
	onInfo: PropTypes.func.isRequired,
	onPlay: PropTypes.func.isRequired,
	eyebrow: PropTypes.string
};

export default HeroBanner;
