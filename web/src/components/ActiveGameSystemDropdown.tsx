import { useState } from 'react'
import { useAppContext } from '../context/AppContext'
import { getErrorMessage } from '../lib/api'
import { GameSystemMenu } from './tags/GameSystemMenu'

export function ActiveGameSystemDropdown() {
    const { activeGameSystem, availableGameSystems, setActiveGameSystem } = useAppContext()
    const [error, setError] = useState('')

    return (
        <div className="active-game-system">
            <GameSystemMenu
                selectedGameSystem={activeGameSystem}
                options={availableGameSystems}
                allowCreate
                placeholder="Select a Game System"
                align="left"
                compact
                className="tag-badge tag-badge--game-system tag-badge--interactive tag-badge--navbar"
                onSelect={async (ruleset) => {
                    try {
                        await setActiveGameSystem(ruleset.id)
                        setError('')
                    } catch (err) {
                        setError(getErrorMessage(err, 'Unable to change the active game system.'))
                    }
                }}
            />
            {error && <p className="active-game-system__error">{error}</p>}
        </div>
    )
}
