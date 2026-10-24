import PropTypes from 'prop-types';
import Spottable from '@enact/spotlight/Spottable';
import Icon from '@enact/limestone/Icon';

import css from './PillButton.module.less';

const SpottableDiv = Spottable('div');

/**
 * Knopf im Stil der Streamingdienste: „Abspielen“ weiß gefüllt, alles andere
 * halbtransparent. Limestones Button sieht nach Systemeinstellung aus, nicht
 * nach Kino.
 *
 * @param {string} [variant] - 'primary' (weiß) oder 'secondary' (Glas)
 * @param {string} [icon] - Limestone-Icon, z. B. 'play'
 * @param {boolean} [selected] - Zustand „an“ (z. B. Favorit), Markenfarbe
 * @param {boolean} [disabled] - während einer Anfrage; Klicks werden ignoriert
 */
const PillButton = ({variant = 'secondary', icon, selected, disabled, onClick, className, children, ...rest}) => {
	const classes = [
		css.pill,
		css[variant],
		selected ? css.selected : '',
		disabled ? css.disabled : '',
		className || ''
	].join(' ');

	return (
		<SpottableDiv
			{...rest}
			role="button"
			className={classes}
			aria-disabled={disabled}
			onClick={disabled ? null : onClick}
		>
			{icon ? <Icon className={css.icon} size="small">{icon}</Icon> : null}
			<span className={css.label}>{children}</span>
		</SpottableDiv>
	);
};

PillButton.propTypes = {
	children: PropTypes.node,
	className: PropTypes.string,
	disabled: PropTypes.bool,
	icon: PropTypes.string,
	onClick: PropTypes.func,
	selected: PropTypes.bool,
	variant: PropTypes.oneOf(['primary', 'secondary'])
};

export default PillButton;
