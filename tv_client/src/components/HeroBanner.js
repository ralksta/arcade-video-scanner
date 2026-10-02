import PropTypes from 'prop-types';
import Button from '@enact/limestone/Button';

import css from './Home.module.less';

/**
 * Großes Titelbild oben auf Home, wie bei Netflix: ein Eintrag mit Bild,
 * Titel, Metadaten und „Abspielen“.
 *
 * @param {Object} video - der hervorgehobene Eintrag
 * @param {string} src - Vorschaubild-URL
 * @param {string} title
 * @param {string} [meta]
 * @param {string} [eyebrow] - kleine Zeile über dem Titel
 * @param {Function} onPlay
 */
const HeroBanner = ({video, src, title, meta, eyebrow, onPlay}) => {
	if (!video) return null;

	return (
		<section className={css.hero}>
			{src ? <img className={css.heroImage} src={src} alt="" /> : null}
			<div className={css.heroShade} />
			<div className={css.heroText}>
				{eyebrow ? <div className={css.heroEyebrow}>{eyebrow}</div> : null}
				<div className={css.heroTitle}>{title}</div>
				{meta ? <div className={css.heroMeta}>{meta}</div> : null}
				<Button icon="play" onClick={onPlay}>Abspielen</Button>
			</div>
		</section>
	);
};

HeroBanner.propTypes = {
	onPlay: PropTypes.func.isRequired,
	title: PropTypes.string.isRequired,
	eyebrow: PropTypes.string,
	meta: PropTypes.string,
	src: PropTypes.string,
	video: PropTypes.object
};

export default HeroBanner;
