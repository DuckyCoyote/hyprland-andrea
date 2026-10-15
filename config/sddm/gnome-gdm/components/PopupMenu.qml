import QtQuick

// Menú flotante oscuro con esquinas redondeadas (estilo popover de GNOME).
// model: [{ text, icon, checked, enabled, action }]
Rectangle {
    id: root

    property var model: []
    property string fontFamily
    property color accent: "#78aeed"
    property real textScale: 1.0
    signal triggered(int index)

    width: Math.max(220, column.implicitWidth + 12)
    height: column.implicitHeight + 12
    radius: 14
    color: "#2e2e32"
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.08)
    visible: false
    opacity: visible ? 1 : 0
    scale: visible ? 1 : 0.96
    Behavior on opacity { NumberAnimation { duration: 120 } }
    Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }

    // Sombra simple
    Rectangle {
        z: -1
        anchors.fill: parent
        anchors.margins: -4
        anchors.topMargin: -2
        anchors.bottomMargin: -8
        radius: parent.radius + 4
        color: Qt.rgba(0, 0, 0, 0.25)
    }

    Column {
        id: column
        x: 6
        y: 6
        width: root.width - 12

        Repeater {
            model: root.model
            delegate: Rectangle {
                id: item
                required property var modelData
                required property int index
                readonly property bool usable: modelData.enabled === undefined || modelData.enabled

                width: column.width
                implicitWidth: row.implicitWidth + 24
                height: Math.round(38 * root.textScale)
                radius: 8
                color: hover.containsMouse && usable ? Qt.rgba(1, 1, 1, 0.08) : "transparent"
                opacity: usable ? 1 : 0.4

                Row {
                    id: row
                    anchors.verticalCenter: parent.verticalCenter
                    x: 12
                    spacing: 12

                    Image {
                        visible: !!item.modelData.icon
                        anchors.verticalCenter: parent.verticalCenter
                        width: 16; height: 16
                        sourceSize: Qt.size(32, 32)
                        source: item.modelData.icon || ""
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: item.modelData.text
                        color: "white"
                        font.family: root.fontFamily
                        font.pixelSize: Math.round(14 * root.textScale)
                    }
                }

                Image {
                    visible: !!item.modelData.checked
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    width: 16; height: 16
                    sourceSize: Qt.size(32, 32)
                    source: Qt.resolvedUrl("../icons/object-select.svg")
                }

                MouseArea {
                    id: hover
                    anchors.fill: parent
                    hoverEnabled: true
                    enabled: item.usable
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.triggered(item.index)
                }
            }
        }
    }
}
