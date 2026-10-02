import PropTypes from 'prop-types';
import Spottable from '@enact/spotlight/Spottable';
import SpotlightContainerDecorator from '@enact/spotlight/SpotlightContainerDecorator';
import Icon from '@enact/limestone/Icon';

import Brand from './Brand';
import css from './TopNav.module.less';

const NavItem = Spottable('div');

// Von unten kommend landet der Fokus auf dem aktiven Bereich, nicht auf dem
// ersten Eintrag.
const NavContainer = SpotlightContainerDecorator(
	{enterTo: 'default-element', defaultElement: '[data-active="true"]'},
	'nav'
);

/**
 * Kopfleiste wie bei Netflix/HBO: Logo, Bereiche als Text, rechts Status und
 * Profil. Über dem Titelbild durchsichtig, beim Scrollen und auf den Rastern
 * deckend.
 *
 * Ersetzt Limestones TabLayout — dessen Reiterleiste sah nach
 * Systemeinstellungen aus.
 *
 * @param {Object[]} items - [{label, icon}]
 * @param {number} index - aktiver Bereich
 * @param {Function} onSelect - bekommt den Index
 * @param {boolean} [solid] - deckender Hintergrund
 * @param {string} [status] - kleine Zeile rechts (Anzahl, Hinweise)
 * @param {string} [user] - Name für das Profil-Kürzel
 */
const TopNav = ({items, index, onSelect, solid, status, user}) => (
	<NavContainer spotlightId="top-nav" className={css.nav + (solid ? ' ' + css.solid : '')}>
		<Brand />
		<div className={css.items}>
			{items.map((item, i) => (
				<NavItem
					key={item.label}
					className={css.item + (i === index ? ' ' + css.active : '')}
					data-active={i === index}
					onClick={() => onSelect(i)}
				>
					{item.icon ? <Icon className={css.itemIcon} size="small">{item.icon}</Icon> : null}
					{item.label}
				</NavItem>
			))}
		</div>
		<div className={css.right}>
			{status ? <span className={css.status}>{status}</span> : null}
			{user ? <span className={css.avatar}>{user.slice(0, 1).toUpperCase()}</span> : null}
		</div>
	</NavContainer>
);

TopNav.propTypes = {
	index: PropTypes.number.isRequired,
	items: PropTypes.arrayOf(PropTypes.shape({
		label: PropTypes.string.isRequired,
		icon: PropTypes.string
	})).isRequired,
	onSelect: PropTypes.func.isRequired,
	solid: PropTypes.bool,
	status: PropTypes.string,
	user: PropTypes.string
};

export default TopNav;
