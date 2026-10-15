import QtQuick
import "components"

// Tema de SDDM que imita la pantalla de acceso de GDM (GNOME, modo oscuro).
Rectangle {
    id: root

    width: 1920
    height: 1080
    color: config.stringValue("background") || "#222226"

    readonly property string fontFamily: config.stringValue("font") || "Adwaita Sans"
    readonly property color accent: config.stringValue("accent") || "#78aeed"
    // SDDM crea una vista por monitor; como GDM, solo el principal muestra el diálogo
    readonly property bool isPrimary: typeof primaryScreen === "undefined" || primaryScreen
    property real textScale: 1.0

    // 0 = lista de usuarios, 1 = contraseña, 2 = «¿No está en la lista?»
    property int view: 0
    property string userName: ""
    property string userRealName: ""
    property string userIcon: ""
    property int sessionIndex: sessionModel.lastIndex >= 0 ? sessionModel.lastIndex : 0
    property bool busy: false
    property string message: ""

    function icon(name) { return Qt.resolvedUrl("icons/" + name + ".svg") }

    function chooseUser(name, realName, face) {
        userName = name
        userRealName = realName
        userIcon = face
        message = ""
        view = 1
        password.clear()
        password.forceActiveFocus()
    }

    function goBack() {
        closeMenus()
        message = ""
        busy = false
        password.clear()
        username.clear()
        view = 0
        userList.forceActiveFocus()
    }

    function login() {
        if (busy) return
        busy = true
        message = ""
        sddm.login(userName, password.text, sessionIndex)
    }

    function closeMenus() {
        powerMenu.visible = false
        sessionMenu.visible = false
        a11yMenu.visible = false
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            root.busy = false
            root.message = "Lo sentimos, eso no ha funcionado. Inténtelo de nuevo."
            password.clear()
            shake.restart()
            password.forceActiveFocus()
        }
        function onLoginSucceeded() { root.busy = false }
    }

    Image {
        anchors.fill: parent
        source: config.stringValue("backgroundImage") || ""
        fillMode: Image.PreserveAspectCrop
        visible: source != ""
        asynchronous: true
    }

    // Clic fuera de un menú lo cierra
    MouseArea {
        anchors.fill: parent
        enabled: powerMenu.visible || sessionMenu.visible || a11yMenu.visible
        z: 50
        onClicked: root.closeMenus()
    }

    // ───────────── Barra superior ─────────────
    Item {
        id: topBar
        width: parent.width
        height: Math.round(32 * root.textScale)
        z: 60

        Text {
            id: clock
            anchors.centerIn: parent
            color: "white"
            font.family: root.fontFamily
            font.pixelSize: Math.round(15 * root.textScale)
            font.weight: Font.Bold

            function update() {
                const now = new Date()
                text = Qt.locale().toString(now, config.stringValue("dateFormat") || "d MMM")
                     + "   " + Qt.locale().toString(now, config.stringValue("timeFormat") || "HH:mm")
            }
            Component.onCompleted: update()

            Timer {
                interval: 1000
                running: true
                repeat: true
                onTriggered: clock.update()
            }
        }

        // Indicadores de estado + menú de apagado
        Rectangle {
            id: statusButton
            anchors.right: parent.right
            anchors.rightMargin: 6
            anchors.verticalCenter: parent.verticalCenter
            height: parent.height - 6
            width: statusRow.implicitWidth + 24
            radius: height / 2
            color: powerMenu.visible ? Qt.rgba(1, 1, 1, 0.2)
                 : statusMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : "transparent"

            Row {
                id: statusRow
                anchors.centerIn: parent
                spacing: 10
                Repeater {
                    model: ["network-wired", "audio-volume-high", "system-shutdown"]
                    Image {
                        required property string modelData
                        width: Math.round(16 * root.textScale); height: width
                        sourceSize: Qt.size(32, 32)
                        source: root.icon(modelData)
                    }
                }
            }

            MouseArea {
                id: statusMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    const open = !powerMenu.visible
                    root.closeMenus()
                    powerMenu.visible = open
                }
            }
        }
    }

    PopupMenu {
        id: powerMenu
        z: 70
        anchors.right: parent.right
        anchors.rightMargin: 8
        y: topBar.height + 6
        transformOrigin: Item.TopRight
        fontFamily: root.fontFamily
        textScale: root.textScale
        model: [
            { text: "Suspender", icon: root.icon("weather-clear-night"), enabled: sddm.canSuspend },
            { text: "Reiniciar…", icon: root.icon("system-reboot"), enabled: sddm.canReboot },
            { text: "Apagar…", icon: root.icon("system-shutdown"), enabled: sddm.canPowerOff }
        ]
        onTriggered: (index) => {
            root.closeMenus()
            if (index === 0) sddm.suspend()
            else if (index === 1) sddm.reboot()
            else sddm.powerOff()
        }
    }

    // ───────────── Diálogo de acceso ─────────────
    Item {
        id: dialog
        visible: root.isPrimary
        anchors.centerIn: parent
        width: Math.round(360 * root.textScale)
        height: parent.height * 0.6

        // Vista 0: lista de usuarios
        Item {
            id: usersView
            anchors.fill: parent
            opacity: root.view === 0 ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 180 } }

            ListView {
                id: userList
                width: parent.width
                height: Math.min(contentHeight, parent.height - 60)
                anchors.centerIn: parent
                anchors.verticalCenterOffset: -20
                spacing: 6
                clip: true
                focus: root.view === 0
                interactive: contentHeight > height
                model: userModel
                currentIndex: userModel.lastIndex >= 0 ? userModel.lastIndex : 0
                keyNavigationWraps: true

                delegate: Rectangle {
                    id: card
                    required property int index
                    required property string name
                    required property string realName
                    required property string icon

                    readonly property string shownName: realName !== "" ? realName : name
                    readonly property bool highlighted: (ListView.isCurrentItem && userList.activeFocus) || cardMouse.containsMouse

                    width: userList.width
                    height: Math.round(68 * root.textScale)
                    radius: 14
                    color: cardMouse.pressed ? Qt.rgba(1, 1, 1, 0.20)
                         : highlighted ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(1, 1, 1, 0.08)
                    border.width: 2
                    border.color: ListView.isCurrentItem && userList.activeFocus ? root.accent : "transparent"
                    Behavior on color { ColorAnimation { duration: 120 } }

                    Avatar {
                        id: cardAvatar
                        x: 10
                        anchors.verticalCenter: parent.verticalCenter
                        size: Math.round(48 * root.textScale)
                        source: card.icon
                    }
                    Text {
                        anchors.left: cardAvatar.right
                        anchors.leftMargin: 14
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        text: card.shownName
                        elide: Text.ElideRight
                        color: "white"
                        font.family: root.fontFamily
                        font.pixelSize: Math.round(16 * root.textScale)
                        font.weight: Font.Bold
                    }
                    MouseArea {
                        id: cardMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.chooseUser(card.name, card.shownName, card.icon)
                    }
                }

                Keys.onReturnPressed: currentItem && root.chooseUser(currentItem.name, currentItem.shownName, currentItem.icon)
                Keys.onEnterPressed: currentItem && root.chooseUser(currentItem.name, currentItem.shownName, currentItem.icon)
            }

            Text {
                id: notListed
                anchors.top: userList.bottom
                anchors.topMargin: 10
                anchors.left: userList.left
                anchors.leftMargin: 6
                text: "¿No está en la lista?"
                color: notListedMouse.containsMouse ? "white" : Qt.rgba(1, 1, 1, 0.85)
                font.family: root.fontFamily
                font.pixelSize: Math.round(13 * root.textScale)
                font.weight: Font.Bold
                font.underline: notListedMouse.containsMouse

                MouseArea {
                    id: notListedMouse
                    anchors.fill: parent
                    anchors.margins: -6
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.message = ""
                        root.view = 2
                        username.clear()
                        username.forceActiveFocus()
                    }
                }
            }
        }

        // Vistas 1 y 2: contraseña / nombre de usuario
        Item {
            id: authView
            anchors.fill: parent
            opacity: root.view !== 0 ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 180 } }

            Column {
                anchors.centerIn: parent
                anchors.verticalCenterOffset: -30
                spacing: 18

                Avatar {
                    anchors.horizontalCenter: parent.horizontalCenter
                    size: Math.round(96 * root.textScale)
                    source: root.view === 1 ? root.userIcon : ""
                    visible: root.view === 1
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: root.view === 1
                    text: root.userRealName
                    color: "white"
                    font.family: root.fontFamily
                    font.pixelSize: Math.round(20 * root.textScale)
                    font.weight: Font.Bold
                }

                Item { width: 1; height: 4; visible: root.view === 1 }

                Item {
                    id: entryRow
                    width: Math.round(400 * root.textScale)
                    height: Math.round(40 * root.textScale)
                    anchors.horizontalCenter: parent.horizontalCenter

                    IconButton {
                        id: backButton
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        width: entryRow.height; height: width
                        icon: root.icon("go-previous")
                        accent: root.accent
                        onClicked: root.goBack()
                    }

                    Item {
                        id: entries
                        anchors.left: backButton.right
                        anchors.right: sessionButton.left
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        height: parent.height

                        SequentialAnimation {
                            id: shake
                            loops: 1
                            NumberAnimation { target: entries; property: "anchors.leftMargin"; to: 22; duration: 50 }
                            NumberAnimation { target: entries; property: "anchors.leftMargin"; to: -2; duration: 70 }
                            NumberAnimation { target: entries; property: "anchors.leftMargin"; to: 18; duration: 70 }
                            NumberAnimation { target: entries; property: "anchors.leftMargin"; to: 2; duration: 70 }
                            NumberAnimation { target: entries; property: "anchors.leftMargin"; to: 10; duration: 50 }
                        }

                        Entry {
                            id: password
                            anchors.fill: parent
                            visible: root.view === 1
                            enabled: !root.busy
                            echoMode: TextInput.Password
                            placeholder: "Contraseña"
                            accent: root.accent
                            fontFamily: root.fontFamily
                            onAccepted: root.login()
                            Keys.onEscapePressed: root.goBack()
                        }

                        Entry {
                            id: username
                            anchors.fill: parent
                            visible: root.view === 2
                            placeholder: "Nombre de usuario"
                            accent: root.accent
                            fontFamily: root.fontFamily
                            onAccepted: if (text.trim() !== "") root.chooseUser(text.trim(), text.trim(), "")
                            Keys.onEscapePressed: root.goBack()
                        }
                    }

                    IconButton {
                        id: sessionButton
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        width: entryRow.height; height: width
                        icon: root.icon("emblem-system")
                        accent: root.accent
                        checked: sessionMenu.visible
                        onClicked: {
                            const open = !sessionMenu.visible
                            root.closeMenus()
                            if (open) sessionMenu.placeBelow(sessionButton)
                            sessionMenu.visible = open
                        }
                    }
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: entryRow.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: root.message !== "" ? root.message
                        : (keyboard.capsLock && root.view === 1 ? "Bloq Mayús está activado" : " ")
                    color: Qt.rgba(1, 1, 1, 0.8)
                    font.family: root.fontFamily
                    font.pixelSize: Math.round(13 * root.textScale)
                }
            }
        }
    }

    // Menú de sesiones (Hyprland, Plasma…), junto al engranaje
    PopupMenu {
        id: sessionMenu
        z: 70
        fontFamily: root.fontFamily
        textScale: root.textScale
        transformOrigin: Item.TopLeft
        // mapToItem no es reactivo en un binding: se calcula al abrir
        function placeBelow(anchor) {
            const p = anchor.mapToItem(root, 0, anchor.height + 8)
            x = Math.max(8, Math.min(p.x, root.width - width - 8))
            y = p.y
        }

        model: {
            const items = []
            for (let i = 0; i < sessionList.count; i++)
                items.push({ text: sessionList.itemAt(i).name, checked: i === root.sessionIndex })
            return items
        }
        onTriggered: (index) => {
            root.sessionIndex = index
            root.closeMenus()
            password.forceActiveFocus()
        }
    }

    // Lee los nombres del modelo de sesiones de SDDM
    Repeater {
        id: sessionList
        model: sessionModel
        delegate: Item {
            required property string name
            visible: false
        }
    }

    // ───────────── Logo y accesibilidad ─────────────
    Image {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Math.round(parent.height * 0.05)
        visible: root.isPrimary && source != ""
        height: Math.round(parent.height * 0.085)
        width: height * 3
        fillMode: Image.PreserveAspectFit
        sourceSize.height: height * 2
        source: {
            const logo = config.stringValue("logo")
            if (!logo) return ""
            return logo.startsWith("/") ? "file://" + logo : Qt.resolvedUrl(logo)
        }
    }

    IconButton {
        id: a11yButton
        visible: root.isPrimary
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 24
        width: Math.round(48 * root.textScale); height: width
        iconSize: 18
        icon: root.icon("preferences-desktop-accessibility")
        accent: root.accent
        checked: a11yMenu.visible
        onClicked: {
            const open = !a11yMenu.visible
            root.closeMenus()
            a11yMenu.visible = open
        }
    }

    PopupMenu {
        id: a11yMenu
        z: 70
        anchors.right: a11yButton.right
        anchors.bottom: a11yButton.top
        anchors.bottomMargin: 8
        transformOrigin: Item.BottomRight
        fontFamily: root.fontFamily
        textScale: root.textScale
        model: [{ text: "Texto grande", checked: root.textScale > 1 }]
        onTriggered: root.textScale = root.textScale > 1 ? 1.0 : 1.25
    }

    Component.onCompleted: userList.forceActiveFocus()
}
