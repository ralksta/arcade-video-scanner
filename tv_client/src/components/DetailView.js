import {useEffect} from 'react';
import PropTypes from 'prop-types';
import Button from '@enact/limestone/Button';
import Spotlight from '@enact/spotlight';
import SpotlightContainerDecorator from '@enact/spotlight/SpotlightContainerDecorator';

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
const DetailView = ({src, title, meta, tags, favorite, busy, resumeLabel, onPlay, onPlayFromStart, onToggleFavorite, onClose}) => {
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
			{src ? <img className={css.image} src={src} alt="" /> : null}
			<div className={css.shade} />
			<div className={css.content}>
				<div className={css.title}>{title}</div>
				{meta ? <div className={css.meta}>{meta}</div> : null}
				{resumeLabel ? <div className={css.resume}>{resumeLabel}</div> : null}
				{tags && tags.length ? (
					<div className={css.tags}>
						{tags.map(t => <span key={t} className={css.tag}>{t}</span>)}
					</div>
				) : null}
				<div className={css.actions}>
					<Button className="spottable-default" icon="play" onClick={onPlay}>
						{resumeLabel ? 'Fortsetzen' : 'Abspielen'}
					</Button>
					{resumeLabel ? <Button icon="refresh" onClick={onPlayFromStart}>Von vorn</Button> : null}
					<Button
						icon={favorite ? 'star' : 'starhollow'}
						selected={favorite}
						disabled={busy}
						onClick={onToggleFavorite}
					>
						{favorite ? 'Favorit' : 'Zu Favoriten'}
					</Button>
					<Button icon="arrowlargeleft" onClick={onClose}>Zurück</Button>
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
	onToggleFavorite: PropTypes.func.isRequired,
	title: PropTypes.string.isRequired,
	busy: PropTypes.bool,
	favorite: PropTypes.bool,
	meta: PropTypes.string,
	src: PropTypes.string,
	tags: PropTypes.arrayOf(PropTypes.string)
};

export default DetailView;
