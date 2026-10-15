import QtQuick

// Campo de texto en forma de píldora, como las entradas de GDM.
FocusScope {
    id: root

    property alias text: input.text
    property alias echoMode: input.echoMode
    property string placeholder
    property color accent: "#78aeed"
    property string fontFamily
    signal accepted()

    implicitWidth: 300
    implicitHeight: 40

    function clear() { input.text = "" }
    function selectAll() { input.selectAll() }

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: Qt.rgba(1, 1, 1, input.activeFocus ? 0.12 : 0.10)
        border.width: 2
        border.color: input.activeFocus ? root.accent : "transparent"
        Behavior on border.color { ColorAnimation { duration: 150 } }
    }

    Text {
        anchors.fill: input
        verticalAlignment: Text.AlignVCenter
        text: root.placeholder
        color: Qt.rgba(1, 1, 1, 0.45)
        font: input.font
        visible: input.text.length === 0
    }

    TextInput {
        id: input
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        verticalAlignment: TextInput.AlignVCenter
        focus: true
        clip: true
        color: "white"
        selectionColor: root.accent
        selectedTextColor: "#1e1e1e"
        passwordCharacter: "●"
        passwordMaskDelay: 0
        font.family: root.fontFamily
        font.pixelSize: 15
        onAccepted: root.accepted()
    }
}
