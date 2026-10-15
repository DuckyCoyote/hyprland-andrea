import QtQuick
import QtQuick.Effects

// Avatar circular: la foto del usuario recortada en círculo, o el icono
// genérico de persona sobre un círculo gris si no hay foto.
Item {
    id: root

    property string source
    property int size: 48

    width: size
    height: size

    // Sin ~/.face.icon, SDDM devuelve la cara genérica de su carpeta faces/
    readonly property bool hasPhoto: source !== ""
        && !/\/faces\/\.face\.icon$/.test(source)
        && photo.status === Image.Ready

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: Qt.rgba(1, 1, 1, 0.15)
        visible: !root.hasPhoto

        Image {
            anchors.centerIn: parent
            width: Math.round(root.size * 0.5)
            height: width
            sourceSize: Qt.size(width * 2, height * 2)
            source: Qt.resolvedUrl("../icons/avatar-default.svg")
        }
    }

    Image {
        id: photo
        anchors.fill: parent
        source: root.source
        sourceSize: Qt.size(root.size * 2, root.size * 2)
        fillMode: Image.PreserveAspectCrop
        visible: false
        layer.enabled: true
    }

    Rectangle {
        id: mask
        anchors.fill: parent
        radius: width / 2
        visible: false
        layer.enabled: true
        layer.smooth: true
    }

    MultiEffect {
        anchors.fill: parent
        source: photo
        maskEnabled: true
        maskSource: mask
        maskThresholdMin: 0.5
        maskSpreadAtMin: 1.0
        visible: root.hasPhoto
    }
}
