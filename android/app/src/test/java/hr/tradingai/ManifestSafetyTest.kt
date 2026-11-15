package hr.tradingai

import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import org.junit.Assert.assertEquals
import org.junit.Test

class ManifestSafetyTest {
    @Test fun initialAppHasNoNetworkOrSecretAccessPermissions() {
        val manifest = DocumentBuilderFactory.newInstance().newDocumentBuilder()
            .parse(File("src/main/AndroidManifest.xml"))
        assertEquals(0, manifest.getElementsByTagName("uses-permission").length)
        val app = manifest.getElementsByTagName("application").item(0)
        assertEquals("false", app.attributes.getNamedItem("android:allowBackup").nodeValue)
    }
}
