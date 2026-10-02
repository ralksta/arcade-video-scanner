import {useEffect} from 'react';
import PropTypes from 'prop-types';
import Spotlight from '@enact/spotlight';
import SpotlightContainerDecorator from '@enact/spotlight/SpotlightContainerDecorator';

import PillButton from './PillButton';
import Backdrop from './Backdrop';
import css from './DetailView.module.less';

// Fokus bleibt in der Ansicht: Ohne Einschränkung sprang er mit den
// Pfeiltasten auf die Kacheln dahinter.
const Container = SpotlightContainerDecorator(
	{enterTo: 'default-element', restrict: 'self-only'},
	'div'
);

const CONTAINER_ID = 'detail-view';

/**
 * Detailansicht vor dem Abspielen, wie bei Netflix: großes Bild, Titel,
 * Metadaten, Tags — und „Abspielen“ sowie „Favorit“.
 *
 * Bisher startete OK auf einer Kachel sofort die Wiedergabe; Favoriten ließen
 * sich auf dem Fernseher gar nicht setzen.
 *
 * Die Zurück-Taste schließt die Ansicht (Capture, damit Panels sie nicht
 * zuerst als „App beenden“ deutet).
 */
const DetailView = ({src, poster, title, meta, badge, kicker, playLabel = 'Abspielen', playIcon = 'play', tags, favorite, busy, resumeLabel, onPlay, onPlayFromStart, onToggleFavorite, onClose}) => {
	useEffect(() => {
		const timer = setTimeout(() => Spotlight.focus(CONTAINER_ID), 0);
		const onBack = (ev) => {
			if (ev.keyCode !== 461 && ev.keyCode !== 27) return;
			ev.preventDefault();
			ev.stopImmediatePropagation();
			onClose();
		};
		document.addEventListener('keydown', onBack, true);
		return () => {
			clearTimeout(timer);
			document.removeEventListener('keydown', onBack, true);
		};
	}, [onClose]);

	return (
		<Container spotlightId={CONTAINER_ID} className={css.detail}>
			<Backdrop className={css.image} poster={poster} fallback={src} />
			<div className={css.shade} />
			<div className={css.content}>
				{kicker ? <div className={css.kicker}>{kicker}</div> : null}
				<div className={css.title}>{title}</div>
				<div className={css.meta}>
					{badge ? <span className={css.badge}>{badge}</span> : null}
					{meta}
				</div>
				{resumeLabel ? <div className={css.resume}>{resumeLabel}</div> : null}
				{tags && tags.length ? (
					<div className={css.tags}>
						{tags.map(t => <span key={t} className={css.tag}>{t}</span>)}
					</div>
				) : null}
				<div className={css.actions}>
					<PillButton variant="primary" className="spottable-default" icon={playIcon} onClick={onPlay}>
						{resumeLabel ? 'Fortsetzen' : playLabel}
					</PillButton>
					{resumeLabel ? <PillButton icon="refresh" onClick={onPlayFromStart}>Von vorn</PillButton> : null}
					<PillButton
						icon={favorite ? 'star' : 'starhollow'}
						selected={favorite}
						disabled={busy}
						onClick={onToggleFavorite}
					>
						{favorite ? 'Favorit' : 'Zu Favoriten'}
					</PillButton>
					<PillButton icon="arrowlargeleft" onClick={onClose}>Zurück</PillButton>
				</div>
			</div>
		</Container>
	);
};

DetailView.propTypes = {
	onClose: PropTypes.func.isRequired,
	onPlay: PropTypes.func.isRequired,
	onPlayFromStart: PropTypes.func,
	resumeLabel: PropTypes.string,
	badge: PropTypes.string,
	kicker: PropTypes.string,
	playIcon: PropTypes.string,
	playLabel: PropTypes.string,
	onToggleFavorite: PropTypes.func.isRequired,
	title: PropTypes.string.isRequired,
	busy: PropTypes.bool,
	favorite: PropTypes.bool,
	meta: PropTypes.string,
	poster: PropTypes.string,
	src: PropTypes.string,
	tags: PropTypes.arrayOf(PropTypes.string)
};

export default DetailView;
