<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<xsl:template match="/">
  <html>
    <head>
      <title>OpenPMU Data</title>
    </head>
    <body>
      <h1>OpenPMU Data</h1>
      <table border="1">
        <tr>
          <th>Format</th>
          <th>Date</th>
          <th>Time</th>
          <th>Frame</th>
          <th>Fs</th>
          <th>n</th>
          <th>bits</th>
          <th>Channels</th>
        </tr>
        <tr>
          <td><xsl:value-of select="OpenPMU/Format"/></td>
          <td><xsl:value-of select="OpenPMU/Date"/></td>
          <td><xsl:value-of select="OpenPMU/Time"/></td>
          <td><xsl:value-of select="OpenPMU/Frame"/></td>
          <td><xsl:value-of select="OpenPMU/Fs"/></td>
          <td><xsl:value-of select="OpenPMU/n"/></td>
          <td><xsl:value-of select="OpenPMU/bits"/></td>
          <td><xsl:value-of select="OpenPMU/Channels"/></td>
        </tr>
      </table>
      <h2>Channels</h2>
      <table border="1">
        <tr>
          <th>Channel</th>
          <th>Name</th>
          <th>Type</th>
          <th>Phase</th>
          <th>Range</th>
          <th>Payload</th>
        </tr>
        <xsl:for-each select="OpenPMU/*[starts-with(name(), 'Channel_')]">
          <tr>
            <td><xsl:value-of select="substring-after(name(), 'Channel_')"/></td>
            <td><xsl:value-of select="Name"/></td>
            <td><xsl:value-of select="Type"/></td>
            <td><xsl:value-of select="Phase"/></td>
            <td><xsl:value-of select="Range"/></td>
            <td><xsl:value-of select="Payload"/></td>
          </tr>
        </xsl:for-each>
      </table>
    </body>
  </html>
</xsl:template>

</xsl:stylesheet>
