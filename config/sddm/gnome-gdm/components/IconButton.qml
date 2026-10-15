import QtQuick

// Botón circular con icono simbólico, al estilo de los botones de GDM.
Item {
    id: root

    property string icon
    property int iconSize: 16
    property bool flat: false        // sin fondo en reposo (barra superior)
    property bool checked: false
    property color accent: "#78aeed"
    signal clicked()

    implicitWidth: 40
    implicitHeight: 40
    activeFocusOnTab: true

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: {
            if (mouse.pressed || root.checked) return Qt.rgba(1, 1, 1, 0.24)
            if (mouse.containsMouse) return Qt.rgba(1, 1, 1, root.flat ? 0.10 : 0.18)
            return root.flat ? "transparent" : Qt.rgba(1, 1, 1, 0.10)
        }
        border.width: root.activeFocus ? 2 : 0
        border.color: root.accent
        Behavior on color { ColorAnimation { duration: 120 } }
    }

    Image {
        anchors.centerIn: parent
        source: root.icon
        width: root.iconSize
        height: root.iconSize
        sourceSize: Qt.size(root.iconSize * 2, root.iconSize * 2)
        smooth: true
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    Keys.onReturnPressed: root.clicked()
    Keys.onEnterPressed: root.clicked()
    Keys.onSpacePressed: root.clicked()
}
