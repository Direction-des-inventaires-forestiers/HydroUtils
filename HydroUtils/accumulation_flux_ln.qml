<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis styleCategories="AllStyleCategories" maxScale="0" version="3.22.6-Białowieża" minScale="1e+08" hasScaleBasedVisibilityFlag="0">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
    <Private>0</Private>
  </flags>
  <temporal mode="0" enabled="0" fetchMode="0">
    <fixedRange>
      <start></start>
      <end></end>
    </fixedRange>
  </temporal>
  <customproperties>
    <Option type="Map">
      <Option type="bool" value="false" name="WMSBackgroundLayer"/>
      <Option type="bool" value="false" name="WMSPublishDataSourceUrl"/>
      <Option type="int" value="0" name="embeddedWidgets/count"/>
      <Option type="QString" value="Value" name="identify/format"/>
    </Option>
  </customproperties>
  <pipe-data-defined-properties>
    <Option type="Map">
      <Option type="QString" value="" name="name"/>
      <Option name="properties"/>
      <Option type="QString" value="collection" name="type"/>
    </Option>
  </pipe-data-defined-properties>
  <pipe>
    <provider>
      <resampling zoomedInResamplingMethod="nearestNeighbour" maxOversampling="2" enabled="false" zoomedOutResamplingMethod="nearestNeighbour"/>
    </provider>
    <rasterrenderer opacity="1" band="1" type="singlebandpseudocolor" classificationMin="1" alphaBand="-1" nodataColor="" classificationMax="22000">
      <rasterTransparency/>
      <minMaxOrigin>
        <limits>None</limits>
        <extent>WholeRaster</extent>
        <statAccuracy>Estimated</statAccuracy>
        <cumulativeCutLower>0.02</cumulativeCutLower>
        <cumulativeCutUpper>0.98</cumulativeCutUpper>
        <stdDevFactor>2</stdDevFactor>
      </minMaxOrigin>
      <rastershader>
        <colorrampshader colorRampType="INTERPOLATED" labelPrecision="4" clip="0" maximumValue="22000" classificationMode="1" minimumValue="1">
          <colorramp type="gradient" name="[source]">
            <Option type="Map">
              <Option type="QString" value="247,251,255,255" name="color1"/>
              <Option type="QString" value="8,48,107,255" name="color2"/>
              <Option type="QString" value="0" name="discrete"/>
              <Option type="QString" value="gradient" name="rampType"/>
              <Option type="QString" value="0.00013637;222,235,247,255:0.000545479;198,219,239,255:0.00222737;158,202,225,255:0.00904587;107,174,214,255:0.0295013;66,146,198,255:0.113596;33,113,181,255:0.368153;8,81,156,255" name="stops"/>
            </Option>
            <prop k="color1" v="247,251,255,255"/>
            <prop k="color2" v="8,48,107,255"/>
            <prop k="discrete" v="0"/>
            <prop k="rampType" v="gradient"/>
            <prop k="stops" v="0.00013637;222,235,247,255:0.000545479;198,219,239,255:0.00222737;158,202,225,255:0.00904587;107,174,214,255:0.0295013;66,146,198,255:0.113596;33,113,181,255:0.368153;8,81,156,255"/>
          </colorramp>
          <item alpha="255" color="#f7fbff" label="1" value="1"/>
          <item alpha="255" color="#deebf7" label="4" value="4"/>
          <item alpha="255" color="#c6dbef" label="12" value="13"/>
          <item alpha="255" color="#9ecae1" label="50" value="50"/>
          <item alpha="255" color="#6baed6" label="200" value="200"/>
          <item alpha="255" color="#4292c6" label="650" value="650"/>
          <item alpha="255" color="#2171b5" label="2500" value="2500"/>
          <item alpha="255" color="#08519c" label="8100" value="8100"/>
          <item alpha="255" color="#08306b" label="22000" value="22000"/>
          <rampLegendSettings direction="0" orientation="2" prefix="ln(" useContinuousLegend="1" maximumLabel="" suffix=")" minimumLabel="">
            <numericFormat id="basic">
              <Option type="Map">
                <Option type="QChar" value="" name="decimal_separator"/>
                <Option type="int" value="6" name="decimals"/>
                <Option type="int" value="0" name="rounding_type"/>
                <Option type="bool" value="false" name="show_plus"/>
                <Option type="bool" value="false" name="show_thousand_separator"/>
                <Option type="bool" value="false" name="show_trailing_zeros"/>
                <Option type="QChar" value="" name="thousand_separator"/>
              </Option>
            </numericFormat>
          </rampLegendSettings>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast brightness="0" gamma="1" contrast="0"/>
    <huesaturation colorizeStrength="100" colorizeOn="0" colorizeGreen="128" grayscaleMode="0" invertColors="0" saturation="0" colorizeBlue="128" colorizeRed="255"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
